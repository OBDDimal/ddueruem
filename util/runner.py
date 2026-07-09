"""Utilities for running external commands in benchmarking contexts."""

import multiprocessing
import os
import signal
import subprocess
import sys
import time as _time
from contextlib import nullcontext
from subprocess import PIPE

import cloudpickle

from .benchmarking import tic, toc
from .cli.status import StatusDisplay

# ---------------------------------------------------------------------------
# Internal subprocess helpers
# ---------------------------------------------------------------------------


def _kill_group(pgid):
    """Send SIGTERM then SIGKILL to process group *pgid*.

    Takes the pgid directly - callers must not pass a pid and rely on
    getpgid(), because that introduces a race with os.setsid() in the child
    and can hit the wrong group (e.g. the forkserver) before setsid runs.
    """
    try:
        os.killpg(pgid, signal.SIGTERM)
        _time.sleep(0.5)
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _kill_pid(pid):
    """Send SIGTERM then SIGKILL to a single process by *pid*.

    Used when the subprocess shares a process group with its parent (inside a
    run_for worker) so that killing by group would also kill the worker itself.
    """
    try:
        os.kill(pid, signal.SIGTERM)
        _time.sleep(0.5)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_with_popen(cmd, cwd, kwargs, timeout=None, capture=True):
    """Run *cmd* via Popen, killing the subprocess on any abnormal exit.

    Parameters
    ----------
    capture:
        When True, stdout/stderr are collected into pipes; when False they are
        inherited from the parent (useful for interactive debug output).

    The session context is detected automatically: if the calling process is
    already a session leader (i.e. we are inside a run_for worker that called
    os.setsid), the subprocess inherits the caller's process group and is
    killed by pid on failure so that run_for's group kill can reach it.
    Otherwise the subprocess is placed in its own process group and killed by
    group, taking all its descendants with it.

    Returns ``(proc, stdout_bytes, stderr_bytes)``.
    """
    stdout = kwargs.get("stdout", PIPE if capture else None)

    if "stdout" in kwargs:
        kwargs.pop("stdout")

    stderr = PIPE if capture else None
    in_worker = os.getpid() == os.getsid(0)
    preexec_fn = None if in_worker else os.setsid
    with subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdout=stdout,
        stderr=stderr,
        preexec_fn=preexec_fn,
        **kwargs,
    ) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except BaseException:
            if in_worker:
                _kill_pid(proc.pid)
            else:
                _kill_group(proc.pid)
            proc.communicate()  # drain pipes and reap before __exit__ runs
            raise
    return proc, out, err


# Grace period (seconds) between SIGTERM (cooperative shutdown) and SIGKILL.
# Long enough for a worker to unwind its `with`/`finally` blocks - including an
# inner via_subprocess that does its own SIGTERM→0.5s→SIGKILL - before we escalate.
_TERM_GRACE = 1.5


# Per-worker flag: set once the parent has asked this worker to stop (SIGTERM).
# After that, the worker must not deliver a result - the parent has already
# recorded the timeout - even if the kill surfaces inside fn as an ordinary
# exception (e.g. a killed subprocess returning non-zero) rather than the
# KeyboardInterrupt the handler raises.
_terminating = False


def _worker_sigterm(signum, frame):
    """Turn SIGTERM into an exception so the worker can clean up before dying.

    SIGTERM's default disposition terminates the process immediately, so no
    `finally`/`__exit__`/`atexit` cleanup runs - temp files created with a `with`
    inside *fn* are leaked, and subprocesses *fn* started are not torn down by
    *fn*'s own handlers.  Raising here unwinds the stack normally instead.
    """
    global _terminating
    _terminating = True
    raise KeyboardInterrupt


def _send(conn, msg):
    """Send *msg*, tolerating a pipe the parent has already closed (after a kill)."""
    try:
        conn.send(msg)
    except BrokenPipeError, OSError:
        pass


def _log_worker_timing(arg, wall, cpu0, children0):
    """Append a wall-vs-CPU breakdown for one fn call to ``$RUNNER_DEBUG``.

    Opt-in diagnostic (no-op unless the env var is set). It splits a job's wall
    time into the worker's own Python CPU (``cpu_self``), the CPU of the
    subprocesses it spawned (``cpu_children``), and whatever is left
    (``blocked`` - time the worker was descheduled / waiting on I/O):

        wall ≈ cpu_self + cpu_children + blocked

    Use it to tell whether a slow job is real compute (which bucket) or
    contention. Written to the file named by ``$RUNNER_DEBUG`` (append) rather
    than stderr, which rich's live display would otherwise swallow.
    """
    path = os.environ.get("RUNNER_DEBUG")
    if not path:
        return
    cpu_self = _time.process_time() - cpu0
    cpu_children = sum(os.times()[2:4]) - children0
    line = (
        f"[runner] arg={arg!r} wall={wall:.1f}s "
        f"cpu_self={cpu_self:.1f}s cpu_children={cpu_children:.1f}s "
        f"blocked={wall - cpu_self - cpu_children:.1f}s\n"
    )
    try:
        with open(path, "a") as f:
            f.write(line)
    except OSError:
        sys.stderr.write(line)


def _run_for_worker(payload, conn):
    """Worker target for run_for child processes.

    *payload* is a cloudpickle blob of ``(fn, arg, kwargs)``. It is serialized by
    value (rather than letting multiprocessing pickle the target by reference) so
    that fn may be a lambda, a closure, a decorated function, or a bound method of
    a dynamically created class - none of which the spawn/forkserver start methods
    can pickle by name. The pipe *conn* is still passed normally (multiprocessing
    transfers its file descriptor).

    Runs in a dedicated process group (via os.setsid) so the parent can kill it
    cleanly by process group without affecting its own group. A SIGTERM handler is
    installed so a timeout / Ctrl+C triggers *cooperative* shutdown: fn's context
    managers and finally blocks run (cleaning up temp files and tearing down any
    subprocess fn spawned) before the worker exits, instead of the process being
    terminated with no cleanup. The parent escalates to SIGKILL only if the worker
    is still alive after ``_TERM_GRACE`` seconds.

    A Pipe connection is used instead of Queue to avoid semaphore allocation -
    Queue semaphores are tracked by the resource-tracker process, and SIGKILL
    prevents their cleanup, leaving the tracker alive as a visible orphan.
    """
    global _terminating
    _terminating = False
    fn, arg, kwargs = cloudpickle.loads(payload)
    os.setsid()
    signal.signal(signal.SIGTERM, _worker_sigterm)
    t0 = _time.perf_counter()
    cpu0 = _time.process_time()  # this worker's own CPU (excl. children)
    children0 = sum(os.times()[2:4])  # cumulative CPU of reaped children so far
    try:
        result = fn(*arg, **kwargs) if isinstance(arg, tuple) else fn(arg, **kwargs)
        wall = _time.perf_counter() - t0
        _log_worker_timing(arg, wall, cpu0, children0)
        if not _terminating:
            _send(conn, ("ok", result, wall))
    except KeyboardInterrupt, SystemExit:
        # Cooperative termination (SIGTERM / Ctrl+C): fn's cleanup has already run
        # during unwinding. Don't send a result - the parent records the timeout.
        pass
    except BaseException as e:
        # If the kill surfaced as an ordinary exception (e.g. a SIGTERM'd
        # subprocess returning non-zero), still stay silent - the parent already
        # decided this is a timeout. Only report genuine fn failures.
        if not _terminating:
            _send(conn, ("err", e, _time.perf_counter() - t0))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class UnexpectedStatuscodeException(Exception):
    """Raised when a subprocess exits with an unexpected return code."""


class Call:
    """Result of a subprocess invocation or a run_for slot.

    For normal via_subprocess results, only returncode / stdout / stderr /
    times are set. For run_for slots that timed out or errored, timed_out or
    error are set and the other fields are None.
    """

    def __init__(
        self,
        returncode,
        stdout=None,
        stderr=None,
        times=None,
        timed_out=False,
        error=None,
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.times = times
        self.timed_out = timed_out
        self.error = error

    def add_time(self, name, time):
        if time:
            self.times[name] = time

    def get_time_total(self):
        return sum([x for x in self.times.values() if x])

    def __repr__(self):
        parts = [f"returncode={self.returncode!r}"]
        if self.stdout is not None:
            parts.append(f"stdout={self.stdout!r}")
        if self.stderr is not None:
            parts.append(f"stderr={self.stderr!r}")
        if self.times is not None:
            parts.append(f"times={self.times!r}")
        if self.timed_out:
            parts.append("timed_out=True")
        if self.error is not None:
            parts.append(f"error={self.error!r}")
        return f'Call({", ".join(parts)})'


def via_subprocess(cmd, cwd=None, rc=0, debug=False, **kwargs):
    """Run *cmd* as a shell command and return a :class:`Call` result.

    Parameters
    ----------
    cmd:
        Shell command string passed verbatim to the shell (``shell=True``).
    cwd:
        Working directory for the subprocess.
    rc:
        Expected return code. Raises :class:`UnexpectedStatuscodeException`
        on mismatch. Pass ``None`` to skip the check.
    debug:
        When True, stdout/stderr are not captured and flow directly to the
        terminal. The returned :class:`Call` will have ``stdout=None`` and
        ``stderr=None``.
    **kwargs:
        Forwarded to :class:`subprocess.Popen`. A ``timeout`` key (seconds)
        is intercepted and used as the ``communicate`` timeout.

    Raises
    ------
    UnexpectedStatuscodeException
        When the process exits with a code other than *rc* (and *rc* is not
        ``None``).
    subprocess.TimeoutExpired
        When *timeout* is set and the process does not finish in time.
    """
    timeout = kwargs.pop("timeout", None)
    ident = f"{hash(cmd)}{_time.time()}"

    tic(ident)
    try:
        proc, out, err = _run_with_popen(
            cmd,
            cwd,
            kwargs,
            timeout=timeout,
            capture=not debug,
        )
    finally:
        elapsed = toc(ident)

    if rc is not None and proc.returncode != rc:
        out_str = out.decode("utf-8") if out else ""
        err_str = err.decode("utf-8") if err else ""
        raise UnexpectedStatuscodeException(
            f"UnexpectedStatuscodeException {proc.returncode} != {rc}\n{out_str}\n{err_str}"
        )

    if debug:
        return Call(proc.returncode, times={"time": elapsed})
    return Call(
        proc.returncode,
        stdout=out.decode("utf-8") if out else None,
        stderr=err.decode("utf-8") if err else None,
        times={"time": elapsed},
    )


def with_timeout(fn, *args, timeout=None, **kwargs):
    """Call *fn(arg)* with a hard wall-clock timeout.

    A thin wrapper around :func:`run_for` for single calls.

    Parameters
    ----------
    fn:
        Callable that accepts a single positional argument.
    arg:
        Argument forwarded to *fn*.
    timeout:
        Time limit in seconds. Raises :class:`TimeoutError` when exceeded.

    Returns
    -------
    Call
        The :class:`Call` for the single run (fn's own Call when it returns one).

    Raises
    ------
    TimeoutError
        When *fn* does not finish within *timeout* seconds.
    Exception
        Any exception raised by *fn* is re-raised here.
    """
    result = run_for(fn, [args], kwargs=kwargs, timeout=timeout, show_progress=False)[0]
    if result.timed_out:
        raise TimeoutError(f"{fn} timed out after {timeout}s")
    if result.error is not None:
        raise result.error
    return result


def run_for(
    fn,
    args,
    kwargs=None,
    action=None,
    progress_style=None,
    timeout=None,
    max_workers=(multiprocessing.cpu_count() // 2 - 1),
    show_progress=True,
):
    """Run *fn(arg)* for each element of *args*, enforcing a per-call timeout.

    Each call runs in a dedicated child process (fresh for every argument) so
    that the timeout can reliably kill *fn* and any subprocesses it spawned.
    Up to *max_workers* calls run in parallel; a non-blocking poll loop checks
    every 50 ms, so finished jobs are collected promptly and the status display
    never drifts past a job's real runtime.

    The reported runtime for each slot is the worker's own measured wall time
    around ``fn`` - it excludes process spawn, queueing and collection latency.

    Parameters
    ----------
    fn:
        Callable invoked once per element of *args*. If it returns a
        :class:`Call` (e.g. via :func:`via_subprocess`) that Call is used as the
        result verbatim; any other return value is wrapped in a Call as its
        ``returncode``.
    args:
        Iterable of arguments. A ``tuple`` element is unpacked as
        ``fn(*arg, **kwargs)``; any other element is passed as ``fn(arg,
        **kwargs)``.
    kwargs:
        Optional dict of keyword arguments forwarded to every ``fn`` call.
    action:
        Optional callback invoked in the parent as ``action(value)`` with the
        raw value returned by a successful ``fn`` call, as each one completes.
    progress_style:
        Optional ``f(args, kwargs) -> list`` producing display labels for the
        status lines (one per argument). Defaults to the arguments themselves.
    timeout:
        Wall-clock time limit in seconds **per argument**. When exceeded the
        worker is asked to stop cooperatively (SIGTERM, which unwinds ``fn``'s
        cleanup), and is SIGKILLed if still alive after ``_TERM_GRACE`` seconds.
        The slot's :class:`Call` has ``timed_out=True``.
    max_workers:
        Maximum number of concurrent worker processes.
    progress:
        When True, show a live rich progress bar and per-argument status lines
        while jobs are running.

    Returns
    -------
    list[Call]
        One :class:`Call` per element of *args*, in the original order. Check
        ``call.timed_out`` or ``call.error`` for abnormal slots.

    Notes
    -----
    No orphaned processes: a worker calls :func:`os.setsid` to own its process
    group, and :func:`via_subprocess` detects that it runs inside such a worker
    and leaves its subprocesses in that group (it does *not* start a new
    session). On timeout or Ctrl+C, run_for signals the whole group, so every
    subprocess in the tree is taken down with the worker; a backstop SIGKILL of
    the group guarantees cleanup even if cooperative shutdown fails.
    """
    args = list(args)
    n = len(args)
    if n == 0:
        return []

    results = [None] * n
    pending = list(range(n))
    running = {}  # i -> {proc, conn, t0, phase, deadline, timed_out}

    if progress_style:
        args_styled = progress_style(args, kwargs)
    else:
        args_styled = args

    cm = StatusDisplay(args_styled) if show_progress else nullcontext()

    reaping = []  # procs that have been told to die, awaiting non-blocking reap

    def _signal(proc, sig):
        """Send *sig* to the worker's process group, falling back to its pid.

        Normally the worker is its own group leader (it called os.setsid), so
        signalling the group also reaches every subprocess it spawned. But there
        is a startup window - forkserver bootstrap, before setsid runs - where no
        group with id ``proc.pid`` exists yet; signalling the pid directly still
        reaches the worker so the timeout is honoured. Missing targets (already
        gone) are ignored.
        """
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            try:
                os.kill(proc.pid, sig)
            except ProcessLookupError:
                pass

    def _retire(proc):
        """SIGKILL the worker's group (no orphans) and queue it for reaping.

        Never blocks: the actual wait happens in :func:`_reap_finished`, so a
        worker that is slow to die can't stall the poll loop (which would let
        *other* jobs run past their own timeout).
        """
        _signal(proc, signal.SIGKILL)
        reaping.append(proc)

    def _reap_finished():
        """Non-blocking sweep: join and drop any retired procs that have exited."""
        for proc in list(reaping):
            proc.join(timeout=0)
            if proc.exitcode is not None:
                reaping.remove(proc)

    with cm as display:

        def _emit(i, result, disp_time):
            """Record *result* for slot *i*, notify the display, drop from running."""
            results[i] = result
            running[i]["conn"].close()
            del running[i]
            if display is not None:
                display.set_done(i, result, disp_time)

        try:
            while pending or running:
                # 1) Fill EVERY free slot (not one per tick) so ramp-up to
                #    max_workers isn't throttled to one worker per 50 ms.
                while pending and len(running) < max_workers:
                    i = pending.pop(0)
                    recv_conn, send_conn = multiprocessing.Pipe(duplex=False)
                    payload = cloudpickle.dumps((fn, args[i], kwargs or {}))
                    proc = multiprocessing.Process(
                        target=_run_for_worker, args=(payload, send_conn)
                    )
                    proc.start()
                    send_conn.close()
                    t0 = _time.perf_counter()
                    running[i] = {
                        "proc": proc,
                        "conn": recv_conn,
                        "t0": t0,
                        "phase": "run",
                        "deadline": None,
                        "timed_out": False,
                    }
                    if display is not None:
                        display.set_running(i, t0)

                # 2) Service running jobs. Every branch below is NON-BLOCKING (no
                #    sleep, no join that can wait), so a finished job is collected
                #    within one 50 ms tick - the live display timer can't drift
                #    past a job's real runtime, and a worker that is slow to die
                #    never stalls the loop (which would let other jobs overrun).
                now = _time.perf_counter()
                for i in list(running):
                    job = running[i]
                    proc, conn, t0 = job["proc"], job["conn"], job["t0"]

                    # (a) Anything readable on the pipe - a delivered result or the
                    #     EOF of the worker exiting.
                    if conn.poll():
                        try:
                            msg = conn.recv()
                        except EOFError:
                            msg = None

                        if job["timed_out"]:
                            # We already initiated termination, so the timeout verdict
                            # stands even if the worker pushed a late message first
                            # (e.g. a SIGTERM'd subprocess surfacing as a non-zero exit
                            # before the worker's own SIGTERM handler ran).
                            wall = now - t0
                            _emit(
                                i,
                                Call(
                                    returncode=None,
                                    timed_out=True,
                                    times={"time": wall},
                                ),
                                wall,
                            )
                        elif msg is not None:
                            # A result delivered before any timeout wins: fn finished.
                            # We report the worker's own runtime (fn_elapsed).
                            status, value, fn_elapsed = msg
                            if status == "ok":
                                if action:
                                    action(value)
                                # Preserve fn's own Call (stdout/stderr/returncode and
                                # its measured times); only wrap a bare return value.
                                result = (
                                    value
                                    if isinstance(value, Call)
                                    else Call(
                                        returncode=value, times={"time": fn_elapsed}
                                    )
                                )
                            elif isinstance(value, subprocess.TimeoutExpired):
                                # Inner via_subprocess timeout: via_subprocess already
                                # tore down its own subprocess; SIGKILL backstop below
                                # mops up anything else in the worker's group.
                                result = Call(
                                    returncode=None,
                                    timed_out=True,
                                    times={"time": fn_elapsed},
                                )
                            else:
                                result = Call(
                                    returncode=None,
                                    error=value,
                                    times={"time": fn_elapsed},
                                )
                            _emit(i, result, fn_elapsed)
                        else:
                            # Pipe closed with no payload and we didn't time it out →
                            # the worker crashed before sending.
                            wall = now - t0
                            _emit(
                                i,
                                Call(
                                    returncode=None,
                                    error=RuntimeError(
                                        f"worker crashed (exitcode {proc.exitcode})"
                                    ),
                                    times={"time": wall},
                                ),
                                wall,
                            )
                        _retire(proc)
                        continue

                    # (b) Termination already requested: finalize once it has exited
                    #     (cooperative cleanup done), or escalate at the grace deadline.
                    if job["phase"] == "term":
                        if not proc.is_alive() or now >= job["deadline"]:
                            wall = now - t0
                            _emit(
                                i,
                                Call(
                                    returncode=None,
                                    timed_out=True,
                                    times={"time": wall},
                                ),
                                wall,
                            )
                            _retire(proc)
                        continue

                    # (c) Over budget → start cooperative termination. SIGTERM the
                    #     group: the worker's handler unwinds fn (cleaning up temp
                    #     files, killing its subprocesses); grandchildren get the
                    #     group SIGTERM directly. SIGKILL follows at the deadline.
                    elapsed = now - t0
                    if timeout is not None and elapsed >= timeout:
                        _signal(proc, signal.SIGTERM)
                        job["phase"] = "term"
                        job["timed_out"] = True
                        job["deadline"] = now + _TERM_GRACE
                        continue

                    # (d) Died without sending anything → crash.
                    if not proc.is_alive():
                        _emit(
                            i,
                            Call(
                                returncode=None,
                                error=RuntimeError(
                                    f"worker crashed (exitcode {proc.exitcode})"
                                ),
                                times={"time": elapsed},
                            ),
                            elapsed,
                        )
                        _retire(proc)
                        continue
                    # else: still running within budget - leave it for the next tick.

                _reap_finished()
                _time.sleep(0.05)

        except KeyboardInterrupt:
            # Cooperative shutdown: SIGTERM all workers (so they clean up temp files
            # and tear down their subprocesses), give them _TERM_GRACE to exit, then
            # SIGKILL any survivors.
            for job in running.values():
                _signal(job["proc"], signal.SIGTERM)
            deadline = _time.perf_counter() + _TERM_GRACE
            while running and _time.perf_counter() < deadline:
                for i in list(running):
                    job = running[i]
                    if not job["proc"].is_alive():
                        wall = _time.perf_counter() - job["t0"]
                        if display is not None:
                            display.set_done(
                                i,
                                Call(
                                    returncode=None,
                                    timed_out=True,
                                    times={"time": wall},
                                ),
                                wall,
                            )
                        job["conn"].close()
                        _retire(job["proc"])
                        del running[i]
                _time.sleep(0.05)
            for i, job in list(running.items()):
                wall = _time.perf_counter() - job["t0"]
                if display is not None:
                    display.set_done(
                        i,
                        Call(returncode=None, timed_out=True, times={"time": wall}),
                        wall,
                    )
                job["conn"].close()
                _retire(job["proc"])
                del running[i]
            raise

    # Final bounded reap so we don't leave zombies behind once the loop is done.
    for proc in reaping:
        proc.join(timeout=1.0)

    return results

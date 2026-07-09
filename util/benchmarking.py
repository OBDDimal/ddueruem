import time

from .exceptions import TimerNotRunning

_timers = {}


def tic(s=None, restart_if_running=False):

    if not restart_if_running and s in _timers:
        raise ValueError(f"Timer {s} already running ({_timers[s]})")

    _timers[s] = time.perf_counter()


def toc(s=None):
    if (time_start := _timers.get(s)) is not None:
        t = time.perf_counter() - time_start
        _timers.pop(s)
        return t
    else:
        raise TimerNotRunning()

"""Live terminal status display for run_for sessions, backed by rich."""

import time as _time

from rich.console import Group
from rich.live import Live
from rich.progress import BarColumn, MofNCompleteColumn, Progress
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

_PENDING = "pending"
_RUNNING = "running"
_DONE = "done"


class _DynamicRenderable:
    """Delegates to StatusDisplay._render() on every Live refresh tick."""

    def __init__(self, display):
        self._display = display

    def __rich_console__(self, console, options):
        yield from console.render(self._display._render(), options)


class StatusDisplay:
    """Context-manager that shows a live run_for progress display.

    The display auto-refreshes at 20 fps via rich's Live background thread.
    Call :meth:`set_running` and :meth:`set_done` as jobs change state;
    no explicit refresh call is needed.

    Parameters
    ----------
    args:
        The argument list passed to run_for (used for display labels).
    """

    def __init__(self, args):
        # State tuple: (_PENDING, None, None) | (_RUNNING, None, t0) | (_DONE, result, wall_elapsed)
        self._items = [[arg, (_PENDING, None, None)] for arg in args]
        self._order = list(self._items)
        self._spinner = Spinner("dots")
        self._progress = Progress(
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            auto_refresh=False,
        )
        self._task = self._progress.add_task("", total=len(self._items))
        self._live = Live(_DynamicRenderable(self), refresh_per_second=20)

    def __enter__(self):
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        self._live.__exit__(*args)

    def log(self, *args, **kwargs):
        """Print above the live display (forwarded to the live console)."""
        self._live.console.print(*args, **kwargs)

    def set_running(self, i, t0):
        """Mark slot *i* as running, started at perf_counter time *t0*."""
        item = self._items[i]
        item[1] = (_RUNNING, None, t0)
        self._order.remove(item)
        self._order.insert(0, item)

    def set_done(self, i, result, wall_elapsed=0.0):
        """Mark slot *i* as finished with the given :class:`Call` *result*.

        *wall_elapsed* is the parent-side wall time for the job and is what
        gets displayed — it covers process startup, fn execution, and any
        subprocess calls, giving an accurate total duration.
        """
        item = self._items[i]
        item[1] = (_DONE, result, wall_elapsed)
        self._order.remove(item)
        insert_pos = sum(1 for it in self._order if it[1][0] == _RUNNING)
        self._order.insert(insert_pos, item)
        done = sum(1 for it in self._items if it[1][0] == _DONE)
        self._progress.update(self._task, completed=done)

    def _render(self):
        table = Table(box=None, show_header=False, padding=(0, 1))
        now = _time.perf_counter()

        for arg, (status, result, extra) in self._order:
            name = str(arg)
            if len(name) > 60:
                name = "…" + name[-59:]

            if status == _PENDING:
                table.add_row(Text("·", style="dim"), Text(name, style="dim"), Text(""))
            elif status == _RUNNING:
                elapsed = now - extra  # extra is t0
                table.add_row(
                    self._spinner.render(now),
                    Text(name),
                    Text(f"({elapsed:.1f}s)", style="dim"),
                )
            elif result.timed_out:
                wall_elapsed = extra
                table.add_row(
                    Text("⏱", style="blue"),
                    Text(name, style="blue"),
                    Text(f"timeout ({wall_elapsed:.1f}s)", style="blue"),
                )
            elif result.error is not None:
                table.add_row(
                    Text("✗", style="bold red"),
                    Text(name, style="red"),
                    Text(str(result.error), style="red"),
                )
            else:
                wall_elapsed = extra  # parent-side wall time, not inner subprocess time
                table.add_row(
                    Text("✓", style="bold green"),
                    Text(name, style="green"),
                    Text(f"({wall_elapsed:.2f}s)", style="green"),
                )

        return Group(self._progress, table)

# -----------------------------------------------------------------------------
# External imports #-----------------------------------------------------------

import sys

# -----------------------------------------------------------------------------
# Internal imports #-----------------------------------------------------------
from . import formatting

# -----------------------------------------------------------------------------

_silent = False
_debug = True


def set_silent(*args):
    global _silent

    print("Called set_silent")
    _silent = True


def set_debug(*args):
    global _debug

    print("Called set_debug")
    _debug = True


def check_noisy(f):
    def handler(*args, **kwargs):
        if not _silent:
            f(*args, **kwargs)

    return handler


def check_debug(f):
    def handler(*args, **kwargs):
        if _debug:
            f(*args, **kwargs)

    return handler


def debug(*args, **kwargs):
    _cli.debug(*args, **kwargs)


def say(*args, **kwargs):
    _cli.say(*args, **kwargs)


def subsay(*args, **kwargs):
    _cli.subsay(*args, **kwargs)


def warn(*args, **kwargs):
    _cli.warn(*args, **kwargs)


def error(*args, **kwargs):
    _cli.error(*args, **kwargs)


class CLI:
    def __init__(self, origin=None):
        self._origin = origin

    @check_noisy
    def say(self, *parts, sep=" ", end="\n", error=False):
        if o := self._origin:
            print(
                f"[{o}]",
                *parts,
                sep=sep,
                end=end,
                file=sys.stderr if error else sys.stdout,
            )
        else:
            print(*parts, sep=sep, end=end, file=sys.stderr if error else sys.stdout)

    @check_noisy
    def subsay(self, *parts, sep=" ", end="\n", error=False):
        if o := self._origin:
            print(
                " " * 2,
                f"[{o}]",
                *parts,
                sep=sep,
                end=end,
                file=sys.stderr if error else sys.stdout,
            )
        else:
            print(
                " " * 2,
                *parts,
                sep=sep,
                end=end,
                file=sys.stderr if error else sys.stdout,
            )

    @check_noisy
    @check_debug
    def debug(self, *parts, **kwargs):

        if isinstance(parts, str):
            parts = (formatting.debug(parts),)
        else:
            ls = []
            for part in parts:
                ls.append(formatting.debug(part))

            parts = tuple(ls)

        self.say(*parts, **kwargs)

    def warn(self, *parts, sep=" ", **kwargs):

        if isinstance(parts, str):
            out = formatting.warn(parts)
        else:
            out = [str(formatting.bold("W:"))]
            out.extend([str(part) for part in parts])
            out = formatting.warn(sep.join(out))

        self.say(str(out), **kwargs)

    def error(self, *parts, sep=" ", **kwargs):

        if isinstance(parts, str):
            out = formatting.warn(parts)
        else:
            out = [str(formatting.bold("E:"))]
            out.extend([str(part) for part in parts])
            out = formatting.warn(sep.join(out))

        self.say(str(out), **kwargs)


_cli = CLI()

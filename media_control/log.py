"""Logging"""

__all__ = [
    "colored",
    "LEVELS",
    "debug",
    "info",
    "warn",
    "error",
    "kawaii",
    "set_level",
]


class LEVELS:
    DEBUG = 5
    INFO = 4
    WARN = 3
    ERROR = 2
    CRITICAL = 1
    NONE = 0


_levels = {
    "debug": 5,
    "info": 4,
    "warn": 3,
    "error": 2,
    "critical": 1,
    "none": 0,
}

_level_attribs: dict[int, dict[str, str]] = {
    LEVELS.DEBUG: {
        "color": "34",
        "prefix": "$",
    },
    LEVELS.INFO: {
        "color": "32",
        "prefix": "*",
    },
    LEVELS.WARN: {
        "color": "33",
        "prefix": "!",
    },
    LEVELS.ERROR: {
        "color": "31",
        "prefix": "X",
    },
}

_level = 5
colored = True


def set_level(lvl: str | int) -> None:
    """Set the logging level.

    Args:
        lvl: The logging level.
    """
    global _level
    if isinstance(lvl, str):
        _level = _levels[lvl]
    else:
        _level = lvl


def _log(lvl: int, *print_args: object):
    if _level < lvl:
        return

    prefix: str = _level_attribs[lvl]["prefix"]
    color: str = _level_attribs[lvl]["color"]

    if colored:
        print(f"\x1b[{color}m({prefix})", *print_args, "\x1b[0m")
    else:
        print(f"({prefix})", *print_args)


def debug(*args: object) -> None:
    _log(LEVELS.DEBUG, *args)


def info(*args: object) -> None:
    _log(LEVELS.INFO, *args)


def warn(*args: object) -> None:
    _log(LEVELS.WARN, *args)


def error(*args: object):
    _log(LEVELS.ERROR, *args)


def kawaii(*args: object):
    if colored:
        s = " ".join(("(♡)", *map(str, args)))
        c = [31, 33, 32, 36, 34, 35]
        r = "".join((f"\x1b[{c[i % len(c)]}m{s[i]}") for i in range(len(s)))
        print(r, "\x1b[0m")
    else:
        print("(♡)", *args)


if __name__ == "__main__":
    debug("Debug")
    info("Info")
    warn("Warning")
    error("Error")
    kawaii("Kawaii")

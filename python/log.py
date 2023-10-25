__name__ = "SanLog"
__all__ = [
    "colored",
    "LEVELS",
    "debug",
    "info",
    "warn",
    "warning",
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


def debug(*args, **kwargs):
    if _level < _levels["debug"]:
        return
    if colored:
        print("\x1b[34m($)", *args, "\x1b[0m", **kwargs)
    else:
        print("($)", *args, **kwargs)


def info(*args, **kwargs):
    if _level < _levels["info"]:
        return
    if colored:
        print("\x1b[32m(*)", *args, "\x1b[0m", **kwargs)
    else:
        print("(*)", *args, **kwargs)


def warn(*args, **kwargs):
    if _level < _levels["warn"]:
        return
    if colored:
        print("\x1b[33m(!)", *args, "\x1b[0m", **kwargs)
    else:
        print("(!)", *args, **kwargs)


warning = warn


def error(*args, **kwargs):
    if _level < _levels["error"]:
        return
    if colored:
        print("\x1b[31m(X)", *args, "\x1b[0m", **kwargs)
    else:
        print("(X)", *args, **kwargs)


def kawaii(*args, **kwargs):
    if colored:
        s = kwargs.get("sep", " ")
        s = s.join(("(♡)", *map(str, args)))
        c = [31, 33, 32, 36, 34, 35]
        r = "".join((f"\x1b[{c[i % len(c)]}m{s[i]}") for i in range(len(s)))
        print(r, "\x1b[0m", **kwargs)
    else:
        print("(♡)", *args, **kwargs)


# import inspect


# def logpath(text):
#     caller_path = inspect.stack()[1][1]
#     print(f"{caller_path}: {text}")


if __name__ == "__main__":
    debug("Debug")
    info("Info")
    warn("Warning")
    error("Error")
    kawaii("Kawaii")

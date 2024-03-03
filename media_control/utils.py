__all__ = ["write_file", "read_file", "read_file_bytes", "CustomFormatter"]
import logging


def write_file(filename: str, contents: str | bytes) -> None:
    """Write contents to a file"""
    if isinstance(contents, str):
        with open(filename, "w", encoding="utf-8") as f:
            f.write(contents)
    elif isinstance(contents, bytes):
        with open(filename, "wb") as f:
            f.write(contents)
    else:
        raise TypeError(
            f"Wrong type. Expected `str` or `bytes`, got `{type(contents)}`"
        )


def read_file(filename: str) -> str:
    """Read a file"""
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()


def read_file_bytes(filename: str) -> bytes:
    """Read a file as bytes"""
    with open(filename, "rb") as f:
        return f.read()


class CustomFormatter(logging.Formatter):

    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    grey = "\x1b[38m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: green,
        logging.INFO: blue,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red,
    }

    def format(self, record) -> str:
        _fmt_p = self._fmt
        color = self.FORMATS.get(record.levelno)

        if color is None or _fmt_p is None:
            return "Bruh"

        formatted = color + super().format(record) + self.reset

        return formatted

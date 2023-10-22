import asyncio
from typing import Callable

__all__ = ["async_callback", "write_file", "read_file", "read_file_bytes"]


def async_callback(func: Callable) -> Callable:
    """Use async function as sync callback"""
    f = lambda *a: asyncio.run(func(*a))
    return f


def write_file(filename: str, contents: str | bytes) -> None:
    """Write contents to a file"""
    if isinstance(contents, str):
        open(filename, "w").write(contents)
    elif isinstance(contents, bytes):
        open(filename, "wb").write(contents)
    else:
        raise TypeError(
            f"Wrong type. Expected `str` or `bytes`, got `{type(contents)}`"
        )


def read_file(filename: str) -> str:
    """Read a file"""
    return open(filename, "r").read()


def read_file_bytes(filename: str) -> bytes:
    """Read a file as bytes"""
    return open(filename, "rb").read()

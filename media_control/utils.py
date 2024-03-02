__all__ = ["write_file", "read_file", "read_file_bytes"]


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

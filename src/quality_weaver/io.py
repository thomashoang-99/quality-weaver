import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _temporary_path(path: Path) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    return Path(temporary_name)


def atomic_write_text(path: Path, content: str) -> None:
    """Write text beside its destination, then atomically replace the destination."""
    temporary_path = _temporary_path(path)
    try:
        temporary_path.write_text(content, encoding="utf-8", newline="")
        _replace_with_retry(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _replace_with_retry(source: Path, destination: Path) -> None:
    deadline = time.monotonic() + 1.0
    while True:
        try:
            source.replace(destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


def atomic_create_text(path: Path, content: str) -> None:
    """Atomically create a complete file, failing if the destination already exists."""
    temporary_path = _temporary_path(path)
    try:
        temporary_path.write_text(content, encoding="utf-8", newline="")
        os.link(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(path: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    """Serialize a short operation using an exclusive, transient lock file."""
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for lock: {path}") from None
            time.sleep(0.01)

    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)

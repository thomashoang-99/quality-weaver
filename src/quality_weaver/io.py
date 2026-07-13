import os
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class LockTimeoutError(TimeoutError):
    """Raised when an operating-system file lock cannot be acquired in time."""


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
    """Serialize an operation with an OS-released lock on a persistent lock file."""
    deadline = time.monotonic() + timeout_seconds
    with path.open("a+b") as lock_file:
        _ensure_lock_byte(lock_file)
        while True:
            try:
                _lock_file(lock_file)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(f"timed out waiting for lock: {path}") from None
                time.sleep(0.01)

        try:
            yield
        finally:
            _unlock_file(lock_file)


def _ensure_lock_byte(lock_file: BinaryIO) -> None:
    lock_file.seek(0, os.SEEK_END)
    if lock_file.tell() == 0:
        lock_file.write(b"\0")
        lock_file.flush()
    lock_file.seek(0)


if sys.platform == "win32":

    def _lock_file(lock_file: BinaryIO) -> None:
        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise BlockingIOError from error

    def _unlock_file(lock_file: BinaryIO) -> None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)

else:

    def _lock_file(lock_file: BinaryIO) -> None:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise BlockingIOError from error

    def _unlock_file(lock_file: BinaryIO) -> None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

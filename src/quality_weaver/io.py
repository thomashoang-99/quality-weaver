from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    """Write text beside its destination, then atomically replace the destination."""
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        temporary_path.write_text(content, encoding="utf-8", newline="")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)

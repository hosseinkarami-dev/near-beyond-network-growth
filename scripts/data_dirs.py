"""Helpers for rebuilding generated data directories from scratch."""

import shutil
from pathlib import Path


def clear_directory(directory: Path, *, allowed_parent: Path) -> None:
    """Remove all contents of one expected generated directory, then recreate it."""
    directory = Path(directory)
    allowed_parent = Path(allowed_parent).resolve()

    if directory.is_symlink():
        raise ValueError(f"Refusing to clear a symlinked data directory: {directory}")

    resolved_directory = directory.resolve()
    if resolved_directory.parent != allowed_parent:
        raise ValueError(
            f"Refusing to clear {resolved_directory}; expected it directly under {allowed_parent}"
        )
    if directory.exists() and not directory.is_dir():
        raise NotADirectoryError(directory)

    if directory.exists():
        for child in directory.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()

    directory.mkdir(parents=True, exist_ok=True)

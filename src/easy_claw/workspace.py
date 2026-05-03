from __future__ import annotations

from pathlib import Path


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def resolve_user_path(workspace_root: Path, requested_path: str | Path) -> Path:
    """Resolve a user-provided path against the workspace root.

    If the path is already absolute it is used as-is; otherwise it is
    resolved relative to *workspace_root*.
    """
    path = Path(requested_path)
    if not path.is_absolute():
        path = workspace_root / path
    return normalize_path(path)


def relative_to_root(path: Path, root: Path) -> Path:
    """Return *path* relative to *root*, falling back to *path* unchanged."""
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def is_outside_workspace(path: Path, root: Path) -> bool:
    """Return True if *path* lies outside the *root* directory."""
    try:
        path.relative_to(root)
    except ValueError:
        return True
    return False

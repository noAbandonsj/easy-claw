from __future__ import annotations

from pathlib import Path


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def resolve_user_path(workspace_root: Path, requested_path: str | Path) -> Path:
    """基于工作区根目录解析用户提供的路径。

    如果传入的是绝对路径，则直接使用；否则按工作区根目录解析。
    """
    path = Path(requested_path)
    if not path.is_absolute():
        path = workspace_root / path
    return normalize_path(path)


def relative_to_root(path: Path, root: Path) -> Path:
    """返回相对 root 的路径；无法相对化时返回原路径。"""
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def is_outside_workspace(path: Path, root: Path) -> bool:
    """如果路径位于工作区外，则返回 True。"""
    try:
        path.relative_to(root)
    except ValueError:
        return True
    return False

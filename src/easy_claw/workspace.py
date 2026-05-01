from __future__ import annotations

import os
from pathlib import Path


class WorkspaceBoundaryError(ValueError):
    """Raised when a requested path escapes the configured workspace root."""


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _same_or_child(root: Path, target: Path) -> bool:
    root_text = os.path.normcase(str(root))
    target_text = os.path.normcase(str(target))
    try:
        return os.path.commonpath([root_text, target_text]) == root_text
    except ValueError:
        return False


def resolve_workspace_path(workspace_root: Path, requested_path: Path) -> Path:
    root = normalize_path(workspace_root)
    candidate = requested_path
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = normalize_path(candidate)

    if not _same_or_child(root, resolved):
        raise WorkspaceBoundaryError(
            f"Path '{requested_path}' is outside workspace root '{workspace_root}'."
        )

    return resolved

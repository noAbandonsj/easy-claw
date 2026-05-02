from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from easy_claw.workspace import normalize_path


@dataclass(frozen=True)
class ReportOutput:
    relative_path: str
    path: Path
    outside_workspace: bool = False


def write_markdown_report(
    workspace_root: Path,
    output_path: str | Path,
    content: str,
) -> ReportOutput:
    root = normalize_path(workspace_root)
    target = Path(output_path)
    if not target.is_absolute():
        target = root / target
    resolved = normalize_path(target)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return ReportOutput(
        relative_path=_relative_to_root(resolved, root).as_posix(),
        path=resolved,
        outside_workspace=_is_outside_workspace(resolved, root),
    )


def _relative_to_root(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _is_outside_workspace(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return True
    return False

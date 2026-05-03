from __future__ import annotations

from pathlib import Path

from easy_claw.tools.core import build_core_tools


def build_agent_tools(*, workspace_path: Path, cwd: Path) -> list[object]:
    """Backward-compatible alias for the default local tool list."""
    return build_core_tools(workspace_path=workspace_path, cwd=cwd)

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

CleanupCallback = Callable[[], None]


@dataclass(frozen=True)
class ToolContext:
    workspace_path: Path
    cwd: Path
    browser_enabled: bool = False
    browser_headless: bool = False


@dataclass(frozen=True)
class ToolBundle:
    tools: list[object] = field(default_factory=list)
    cleanup: Sequence[CleanupCallback] = field(default_factory=tuple)

    def close(self) -> None:
        for callback in self.cleanup:
            callback()

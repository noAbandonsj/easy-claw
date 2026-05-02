from __future__ import annotations


class ToolExecutionError(RuntimeError):
    """Raised when a local tool cannot complete the requested operation."""

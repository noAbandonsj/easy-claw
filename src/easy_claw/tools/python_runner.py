from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from easy_claw.tools.commands import CommandResult, run_command


def run_python_code(
    code: str,
    *,
    cwd: Path,
    timeout_seconds: int = 60,
    max_output_chars: int = 20_000,
) -> CommandResult:
    workdir = Path(cwd)
    script_path = workdir / f".easy_claw_{uuid4().hex}.py"
    script_path.write_text(code, encoding="utf-8")
    try:
        return run_command(
            f'python "{script_path.name}"',
            cwd=workdir,
            timeout_seconds=timeout_seconds,
            max_output_chars=max_output_chars,
        )
    finally:
        script_path.unlink(missing_ok=True)

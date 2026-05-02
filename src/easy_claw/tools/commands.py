from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    command: str
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool


def run_command(
    command: str,
    *,
    cwd: Path,
    timeout_seconds: int = 60,
    max_output_chars: int = 20_000,
) -> CommandResult:
    timed_out = False
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _build_powershell_command(command)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = _decode_timeout_output(exc.stdout)
        stderr = _decode_timeout_output(exc.stderr)

    stdout, stdout_truncated = _truncate(stdout, max_output_chars)
    stderr, stderr_truncated = _truncate(stderr, max_output_chars)
    return CommandResult(
        command=command,
        cwd=Path(cwd),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        truncated=stdout_truncated or stderr_truncated,
    )


def _truncate(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return value[:max_chars], True


def _build_powershell_command(command: str) -> str:
    return f"{command}; if ($null -ne $LASTEXITCODE) {{ exit $LASTEXITCODE }}"


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value

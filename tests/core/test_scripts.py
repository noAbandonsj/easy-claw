import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not locate project root")


ROOT = _project_root()


def test_mcp_setup_uses_generic_script_and_start_flag():
    setup_script = (ROOT / "scripts" / "setup-mcp.ps1").read_text(encoding="utf-8")
    start_script = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert (ROOT / "scripts" / "setup-mcp.ps1").exists()
    assert not (ROOT / "scripts" / "setup-memory.ps1").exists()
    assert "[switch]$Mcp" in start_script
    assert "setup-mcp.ps1" in start_script
    assert "setup-memory.ps1" not in start_script
    assert "[switch]$Memory" not in start_script
    assert ".\\scripts\\start.ps1 -Mcp" in readme
    assert ".\\scripts\\setup-mcp.ps1" in readme
    assert "start.ps1 -Memory" not in readme
    assert "setup-memory.ps1" not in readme
    assert ".\\scripts\\start.ps1 -Mcp" in env_example
    assert "mcp-server-git" in setup_script
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in setup_script
    assert "AMAP_MAPS_API_KEY" in setup_script
    assert "@amap/amap-maps-mcp-server" in setup_script


def _powershell_command() -> list[str]:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required to test start.ps1")
    return [executable, "-NoProfile", "-ExecutionPolicy", "Bypass"]


def test_start_script_runs_uv_from_project_root_when_called_from_elsewhere(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "uv.log"
    (bin_dir / "uv.cmd").write_text(
        textwrap.dedent(
            r"""
            @echo off
            echo %CD%^|%*>>"%UV_LOG%"
            exit /b 0
            """
        ).strip(),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "UV_LOG": str(log_path),
    }

    result = subprocess.run(
        [*_powershell_command(), "-File", str(ROOT / "scripts" / "start.ps1")],
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    entries = [line.split("|", 1) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert entries
    assert {Path(cwd).resolve() for cwd, _args in entries} == {ROOT}


def test_start_script_stops_when_uv_command_fails(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "uv.log"
    (bin_dir / "uv.cmd").write_text(
        textwrap.dedent(
            r"""
            @echo off
            echo %*>>"%UV_LOG%"
            exit /b 23
            """
        ).strip(),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "UV_LOG": str(log_path),
    }

    result = subprocess.run(
        [*_powershell_command(), "-File", str(ROOT / "scripts" / "start.ps1")],
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode != 0
    assert log_path.read_text(encoding="utf-8").splitlines() == ["sync"]


def test_start_script_prints_windows_install_command_when_uv_is_missing(tmp_path: Path):
    env = {
        **os.environ,
        "PATH": str(tmp_path),
    }

    result = subprocess.run(
        [*_powershell_command(), "-File", str(ROOT / "scripts" / "start.ps1")],
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "winget install --id=astral-sh.uv -e" in output
    assert "https://docs.astral.sh/uv/getting-started/installation/" in output

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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

from typer.testing import CliRunner

from easy_claw.cli import app


def test_doctor_command_reports_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CLAW_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "easy-claw doctor" in result.stdout

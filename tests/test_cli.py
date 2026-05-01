from typer.testing import CliRunner

from easy_claw.cli import app


def test_doctor_command_reports_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CLAW_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "easy-claw doctor" in result.stdout


def test_chat_dry_run_uses_fake_runtime():
    runner = CliRunner()

    result = runner.invoke(app, ["chat", "--dry-run", "hello"])

    assert result.exit_code == 0
    assert "easy-claw dry run: hello" in result.stdout


def test_chat_without_model_reports_configuration_error(monkeypatch):
    monkeypatch.delenv("EASY_CLAW_MODEL", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["chat", "hello"])

    assert result.exit_code != 0
    assert "Set EASY_CLAW_MODEL" in result.stdout

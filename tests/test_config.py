from easy_claw.config import load_config


def test_load_config_uses_local_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CLAW_DATA_DIR", raising=False)

    config = load_config(cwd=tmp_path)

    assert config.data_dir == tmp_path / "data"
    assert config.product_db_path == tmp_path / "data" / "easy-claw.db"
    assert config.checkpoint_db_path == tmp_path / "data" / "checkpoints.sqlite"


def test_load_config_reads_env_overrides(tmp_path, monkeypatch):
    data_dir = tmp_path / "custom-data"
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("EASY_CLAW_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EASY_CLAW_WORKSPACE", str(workspace))
    monkeypatch.setenv("EASY_CLAW_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("EASY_CLAW_DEVELOPER_MODE", "true")

    config = load_config(cwd=tmp_path)

    assert config.data_dir == data_dir
    assert config.default_workspace == workspace
    assert config.model == "openai:gpt-4.1-mini"
    assert config.developer_mode is True

import os

from easy_claw.config import load_config


def test_load_config_uses_local_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CLAW_DATA_DIR", raising=False)
    monkeypatch.delenv("EASY_CLAW_APPROVAL_MODE", raising=False)
    monkeypatch.delenv("EASY_CLAW_EXECUTION_MODE", raising=False)

    config = load_config(cwd=tmp_path)

    assert config.data_dir == tmp_path / "data"
    assert config.product_db_path == tmp_path / "data" / "easy-claw.db"
    assert config.checkpoint_db_path == tmp_path / "data" / "checkpoints.sqlite"
    assert config.approval_mode == "permissive"
    assert config.execution_mode == "local"


def test_load_config_reads_env_overrides(tmp_path, monkeypatch):
    data_dir = tmp_path / "custom-data"
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("EASY_CLAW_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EASY_CLAW_WORKSPACE", str(workspace))
    monkeypatch.setenv("EASY_CLAW_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("EASY_CLAW_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("EASY_CLAW_API_KEY", "sk-test")
    monkeypatch.setenv("EASY_CLAW_APPROVAL_MODE", "balanced")
    monkeypatch.setenv("EASY_CLAW_EXECUTION_MODE", "local")

    config = load_config(cwd=tmp_path)

    assert config.data_dir == data_dir
    assert config.default_workspace == workspace
    assert config.model == "deepseek-v4-pro"
    assert config.base_url == "https://api.example.com"
    assert config.api_key == "sk-test"
    assert config.approval_mode == "balanced"
    assert config.execution_mode == "local"


def test_load_config_defaults_base_url_to_deepseek(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CLAW_BASE_URL", raising=False)
    monkeypatch.delenv("EASY_CLAW_API_KEY", raising=False)

    config = load_config(cwd=tmp_path)

    assert config.base_url == "https://api.deepseek.com"
    assert config.api_key is None


def test_load_config_reads_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CLAW_MODEL", raising=False)
    (tmp_path / ".env").write_text(
        "EASY_CLAW_MODEL=deepseek-v4-pro",
        encoding="utf-8",
    )

    config = load_config(cwd=tmp_path)

    assert config.model == "deepseek-v4-pro"


def test_load_config_prefers_process_env_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "EASY_CLAW_MODEL=deepseek-from-dotenv",
    )

    monkeypatch.setenv("EASY_CLAW_MODEL", "deepseek-from-process")

    config = load_config(cwd=tmp_path)

    assert config.model == "deepseek-from-process"


def test_load_config_api_key_falls_back_to_deepseek_env(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CLAW_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-deepseek-env")

    config = load_config(cwd=tmp_path)

    assert config.api_key == "from-deepseek-env"


def test_load_config_easy_claw_api_key_takes_priority_over_deepseek(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CLAW_API_KEY", "from-easy-claw")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-deepseek")

    config = load_config(cwd=tmp_path)

    assert config.api_key == "from-easy-claw"


def test_load_config_exports_dotenv_values_for_provider_libraries(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CLAW_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "EASY_CLAW_API_KEY=from-dotenv",
    )

    load_config(cwd=tmp_path)

    assert os.environ.get("EASY_CLAW_API_KEY") == "from-dotenv"

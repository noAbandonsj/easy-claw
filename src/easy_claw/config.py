from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


@dataclass(frozen=True)
class AppConfig:
    cwd: Path
    data_dir: Path
    product_db_path: Path
    checkpoint_db_path: Path
    default_workspace: Path
    model: str | None
    base_url: str
    api_key: str | None


def _read_path(value: str | None, default: Path) -> Path:
    if value is None or value.strip() == "":
        return default
    return Path(value).expanduser()


def load_config(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    current_dir = (cwd or Path.cwd()).resolve()
    dotenv_path = current_dir / ".env"

    if env is None:
        load_dotenv(dotenv_path)
        values = os.environ
    else:
        values = {**dotenv_values(dotenv_path), **env}

    data_dir = _read_path(values.get("EASY_CLAW_DATA_DIR"), current_dir / "data")
    default_workspace = _read_path(values.get("EASY_CLAW_WORKSPACE"), current_dir)

    model = values.get("EASY_CLAW_MODEL") or None
    base_url = values.get("EASY_CLAW_BASE_URL") or "https://api.deepseek.com"
    # Backward compat: fall back to DEEPSEEK_API_KEY if EASY_CLAW_API_KEY not set
    api_key = values.get("EASY_CLAW_API_KEY") or values.get("DEEPSEEK_API_KEY") or None

    return AppConfig(
        cwd=current_dir,
        data_dir=data_dir,
        product_db_path=data_dir / "easy-claw.db",
        checkpoint_db_path=data_dir / "checkpoints.sqlite",
        default_workspace=default_workspace,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )

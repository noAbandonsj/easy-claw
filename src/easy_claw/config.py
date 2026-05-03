from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from easy_claw.defaults import DEFAULT_MAX_MODEL_CALLS, DEFAULT_MAX_TOOL_CALLS


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
    approval_mode: str = "permissive"
    execution_mode: str = "local"
    browser_enabled: bool = False
    browser_headless: bool = False
    max_model_calls: int | None = DEFAULT_MAX_MODEL_CALLS
    max_tool_calls: int | None = DEFAULT_MAX_TOOL_CALLS


def _read_path(value: str | None, default: Path) -> Path:
    if value is None or value.strip() == "":
        return default
    return Path(value).expanduser()


def _read_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_optional_int(value: str | None, default: int | None) -> int | None:
    if value is None or value.strip() == "":
        return default
    parsed = int(value)
    return parsed if parsed > 0 else None


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
    approval_mode = (values.get("EASY_CLAW_APPROVAL_MODE") or "permissive").strip().lower()
    execution_mode = (values.get("EASY_CLAW_EXECUTION_MODE") or "local").strip().lower()
    browser_enabled = _read_bool(values.get("EASY_CLAW_BROWSER_ENABLED"), default=False)
    browser_headless = _read_bool(values.get("EASY_CLAW_BROWSER_HEADLESS"), default=False)
    max_model_calls = _read_optional_int(
        values.get("EASY_CLAW_MAX_MODEL_CALLS"),
        default=DEFAULT_MAX_MODEL_CALLS,
    )
    max_tool_calls = _read_optional_int(
        values.get("EASY_CLAW_MAX_TOOL_CALLS"),
        default=DEFAULT_MAX_TOOL_CALLS,
    )

    return AppConfig(
        cwd=current_dir,
        data_dir=data_dir,
        product_db_path=data_dir / "easy-claw.db",
        checkpoint_db_path=data_dir / "checkpoints.sqlite",
        default_workspace=default_workspace,
        model=model,
        base_url=base_url,
        api_key=api_key,
        approval_mode=approval_mode,
        execution_mode=execution_mode,
        browser_enabled=browser_enabled,
        browser_headless=browser_headless,
        max_model_calls=max_model_calls,
        max_tool_calls=max_tool_calls,
    )

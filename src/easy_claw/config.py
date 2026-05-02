from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    cwd: Path
    data_dir: Path
    product_db_path: Path
    checkpoint_db_path: Path
    default_workspace: Path
    model: str | None
    developer_mode: bool


def _read_bool(value: str | None) -> bool:
    return value is not None and value.strip().lower() in TRUE_VALUES


def _read_path(value: str | None, default: Path) -> Path:
    if value is None or value.strip() == "":
        return default
    return Path(value).expanduser()


def _read_dotenv(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _merge_env(process_env: Mapping[str, str], dotenv_values: Mapping[str, str]) -> dict[str, str]:
    merged = dict(dotenv_values)
    merged.update(process_env)
    return merged


def _export_dotenv_defaults(dotenv_values: Mapping[str, str]) -> None:
    for key, value in dotenv_values.items():
        if value and key not in os.environ:
            os.environ[key] = value


def load_config(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    current_dir = (cwd or Path.cwd()).resolve()
    process_env = env or os.environ
    dotenv_values = _read_dotenv(current_dir / ".env")
    if env is None:
        _export_dotenv_defaults(dotenv_values)
    values = _merge_env(process_env, dotenv_values)

    data_dir = _read_path(values.get("EASY_CLAW_DATA_DIR"), current_dir / "data")
    default_workspace = _read_path(values.get("EASY_CLAW_WORKSPACE"), current_dir)

    return AppConfig(
        cwd=current_dir,
        data_dir=data_dir,
        product_db_path=data_dir / "easy-claw.db",
        checkpoint_db_path=data_dir / "checkpoints.sqlite",
        default_workspace=default_workspace,
        model=values.get("EASY_CLAW_MODEL") or None,
        developer_mode=_read_bool(values.get("EASY_CLAW_DEVELOPER_MODE")),
    )

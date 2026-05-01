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


def load_config(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    current_dir = (cwd or Path.cwd()).resolve()
    values = env or os.environ

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

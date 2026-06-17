from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from easy_claw.api.app import create_app
from easy_claw.config import AppConfig


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model="deepseek-v4-pro",
        base_url="https://api.example.com",
        api_key="sk-test",
        mcp_mode="disabled",
    )


def test_react_app_route_serves_dist_index(tmp_path, monkeypatch):
    dist = tmp_path / "frontend" / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<div id="root"></div><script type="module" src="/app/assets/index.js"></script>',
        encoding="utf-8",
    )
    (assets / "index.js").write_text("console.log('easy-claw react')", encoding="utf-8")

    monkeypatch.setattr("easy_claw.api.app._react_dist_dir", lambda: dist)
    client = TestClient(create_app(_config(tmp_path)))

    app_response = client.get("/app")
    nested_response = client.get("/app/sessions")
    asset_response = client.get("/app/assets/index.js")

    assert app_response.status_code == 200
    assert 'id="root"' in app_response.text
    assert nested_response.status_code == 200
    assert asset_response.status_code == 200
    assert "easy-claw react" in asset_response.text


def test_react_app_route_returns_404_when_dist_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("easy_claw.api.app._react_dist_dir", lambda: tmp_path / "missing")
    client = TestClient(create_app(_config(tmp_path)))

    response = client.get("/app")

    assert response.status_code == 404
    assert response.json()["detail"] == "React web UI has not been built"


def test_root_serves_react_app_after_cutover(tmp_path, monkeypatch):
    dist = tmp_path / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    monkeypatch.setattr("easy_claw.api.app._react_dist_dir", lambda: dist)

    client = TestClient(create_app(_config(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="root"' in response.text

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def _package_json() -> dict[str, object]:
    return json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))


def test_frontend_workspace_has_react_vite_entrypoints() -> None:
    package_json = _package_json()

    assert package_json["private"] is True
    assert package_json["type"] == "module"

    for path in [
        FRONTEND / "index.html",
        FRONTEND / "tsconfig.json",
        FRONTEND / "tsconfig.node.json",
        FRONTEND / "vite.config.ts",
        FRONTEND / "src" / "main.tsx",
        FRONTEND / "src" / "App.tsx",
        FRONTEND / "src" / "styles.css",
        FRONTEND / "src" / "test" / "setup.ts",
    ]:
        assert path.is_file()


def test_frontend_package_defines_expected_scripts_and_dependencies() -> None:
    package_json = _package_json()

    assert package_json["scripts"] == {
        "dev": "vite --host 127.0.0.1",
        "build": "tsc -b && vite build",
        "preview": "vite preview --host 127.0.0.1",
        "test": "vitest",
        "test:run": "vitest run",
        "lint": "eslint .",
    }

    dependencies = package_json["dependencies"]
    assert set(dependencies) == {"react", "react-dom", "react-markdown", "remark-gfm"}

    dev_dependencies = package_json["devDependencies"]
    for name in [
        "@testing-library/jest-dom",
        "@testing-library/react",
        "@types/react",
        "@types/react-dom",
        "@vitejs/plugin-react",
        "eslint",
        "eslint-plugin-react-hooks",
        "eslint-plugin-react-refresh",
        "jsdom",
        "typescript",
        "typescript-eslint",
        "vite",
        "vitest",
    ]:
        assert name in dev_dependencies


def test_vite_config_uses_app_base_and_jsdom_setup() -> None:
    vite_config = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")

    assert "base: '/app/'" in vite_config
    assert "environment: 'jsdom'" in vite_config
    assert "setupFiles: './src/test/setup.ts'" in vite_config

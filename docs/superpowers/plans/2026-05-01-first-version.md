# First Version Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable easy-claw skeleton: CLI first, thin FastAPI foundation, SQLite product storage, workspace-bounded helpers, Markdown skills, explicit product memory, and a LangChain/Deep Agents runtime adapter.

**Architecture:** easy-claw owns configuration, Windows path handling, local product storage, CLI/API presentation, and risk policy. Agent execution is delegated to Deep Agents where possible, with a direct LangChain `create_agent` fallback behind a small `AgentRuntime` interface. LangGraph SQLite checkpointing owns short-term conversation state; easy-claw SQLite tables own product metadata and explicit memory.

**Tech Stack:** Python 3.11+, uv, Typer, Rich, FastAPI, Uvicorn, SQLite, pytest, Ruff, LangChain, LangGraph, Deep Agents, MarkItDown.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, CLI script, pytest and ruff config.
- Create `src/easy_claw/__init__.py`: package version.
- Create `src/easy_claw/config.py`: environment-backed app configuration.
- Create `src/easy_claw/workspace.py`: Windows-safe workspace boundary checks.
- Create `src/easy_claw/storage/db.py`: SQLite schema creation and connection helpers.
- Create `src/easy_claw/storage/repositories.py`: session, memory, and audit repositories.
- Create `src/easy_claw/skills.py`: Markdown skill discovery for `.md` files and Deep Agents style `SKILL.md` folders.
- Create `src/easy_claw/agent/runtime.py`: agent request/result dataclasses and Deep Agents runtime adapter with lazy imports.
- Create `src/easy_claw/api/main.py`: FastAPI app factory and core routes.
- Create `src/easy_claw/cli.py`: Typer CLI commands.
- Create `skills/core/analyze-project/SKILL.md`: built-in project analysis skill.
- Create `skills/core/summarize-docs/SKILL.md`: built-in document summary skill.
- Create `skills/user/.gitkeep`: keeps the user skill directory in git before user-authored skills exist.
- Create `scripts/start.ps1`: Windows start script.
- Create `scripts/doctor.ps1`: Windows diagnostic script.
- Create tests under `tests/`.

## Task 1: Bootstrap Package and Test Harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/easy_claw/__init__.py`
- Create: `tests/test_package.py`

- [ ] **Step 1: Write the failing package import test**

```python
from easy_claw import __version__


def test_package_exposes_version():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Add project config without package implementation**

Add `pyproject.toml` with the package name, `src` layout, pytest config, and dependencies. Do not add `src/easy_claw/__init__.py` yet.

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_package.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'easy_claw'`.

- [ ] **Step 4: Add the minimal package**

Create `src/easy_claw/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_package.py -q`

Expected: `1 passed`.

## Task 2: Config and Workspace Boundaries

**Files:**
- Create: `src/easy_claw/config.py`
- Create: `src/easy_claw/workspace.py`
- Create: `tests/test_config.py`
- Create: `tests/test_workspace.py`

- [ ] **Step 1: Write failing config tests**

```python
from pathlib import Path

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
```

- [ ] **Step 2: Run config tests to verify they fail**

Run: `uv run pytest tests/test_config.py -q`

Expected: FAIL because `easy_claw.config` does not exist.

- [ ] **Step 3: Implement config**

Implement `AppConfig` and `load_config` with `pathlib.Path`, `os.environ`, and boolean parsing for `1`, `true`, `yes`, `on`.

- [ ] **Step 4: Run config tests to verify they pass**

Run: `uv run pytest tests/test_config.py -q`

Expected: all config tests pass.

- [ ] **Step 5: Write failing workspace tests**

```python
from pathlib import Path

import pytest

from easy_claw.workspace import WorkspaceBoundaryError, resolve_workspace_path


def test_resolve_workspace_path_allows_child_path(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "docs" / "README.md"

    resolved = resolve_workspace_path(workspace, Path("docs") / "README.md")

    assert resolved == target.resolve()


def test_resolve_workspace_path_rejects_parent_escape(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(WorkspaceBoundaryError):
        resolve_workspace_path(workspace, Path("..") / "outside.txt")
```

- [ ] **Step 6: Run workspace tests to verify they fail**

Run: `uv run pytest tests/test_workspace.py -q`

Expected: FAIL because `easy_claw.workspace` does not exist.

- [ ] **Step 7: Implement workspace boundary checks**

Implement `WorkspaceBoundaryError`, `normalize_path`, and `resolve_workspace_path`. Use `Path.resolve(strict=False)` and `os.path.commonpath` so Windows paths are compared safely.

- [ ] **Step 8: Run workspace tests to verify they pass**

Run: `uv run pytest tests/test_workspace.py -q`

Expected: all workspace tests pass.

## Task 3: Product SQLite Storage

**Files:**
- Create: `src/easy_claw/storage/__init__.py`
- Create: `src/easy_claw/storage/db.py`
- Create: `src/easy_claw/storage/repositories.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

```python
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import MemoryRepository, SessionRepository


def test_initialize_product_db_creates_tables(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)

    assert db_path.exists()


def test_session_repository_creates_and_lists_sessions(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = SessionRepository(db_path)

    session = repo.create_session(workspace_path=str(tmp_path), model="test:model")

    assert session.id
    assert repo.list_sessions()[0].id == session.id


def test_memory_repository_round_trips_memory_items(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = MemoryRepository(db_path)

    item = repo.remember(scope="project", key="decision", content="CLI first")

    assert repo.list_memory()[0].id == item.id
    assert repo.list_memory()[0].content == "CLI first"
```

- [ ] **Step 2: Run storage tests to verify they fail**

Run: `uv run pytest tests/test_storage.py -q`

Expected: FAIL because storage modules do not exist.

- [ ] **Step 3: Implement SQLite schema and repositories**

Create schema for `sessions`, `memory_items`, and `audit_logs`. Use `sqlite3`, ISO timestamps, and dataclasses for returned rows.

- [ ] **Step 4: Run storage tests to verify they pass**

Run: `uv run pytest tests/test_storage.py -q`

Expected: all storage tests pass.

## Task 4: Skills Discovery

**Files:**
- Create: `src/easy_claw/skills.py`
- Create: `skills/core/analyze-project/SKILL.md`
- Create: `skills/core/summarize-docs/SKILL.md`
- Create: `skills/user/.gitkeep`
- Create: `tests/test_skills.py`

- [ ] **Step 1: Write failing skills tests**

```python
from easy_claw.skills import discover_skills


def test_discover_skills_reads_deep_agents_style_skill(tmp_path):
    skill_dir = tmp_path / "skills" / "core" / "analyze-project"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: analyze-project\ndescription: Analyze a local project.\n---\n# Skill\nRead files.",
        encoding="utf-8",
    )

    skills = discover_skills(tmp_path / "skills")

    assert [skill.name for skill in skills] == ["analyze-project"]
    assert skills[0].description == "Analyze a local project."
    assert "Read files." in skills[0].body


def test_discover_skills_reads_flat_markdown_skill(tmp_path):
    skill_root = tmp_path / "skills" / "core"
    skill_root.mkdir(parents=True)
    (skill_root / "summarize-docs.md").write_text(
        "---\nname: summarize-docs\ndescription: Summarize docs.\n---\n# Skill\nSummarize.",
        encoding="utf-8",
    )

    skills = discover_skills(tmp_path / "skills")

    assert skills[0].name == "summarize-docs"
```

- [ ] **Step 2: Run skills tests to verify they fail**

Run: `uv run pytest tests/test_skills.py -q`

Expected: FAIL because `easy_claw.skills` does not exist.

- [ ] **Step 3: Implement skills discovery**

Parse simple YAML-like frontmatter without adding a dependency. Return `Skill` dataclasses with `name`, `description`, `path`, and `body`.

- [ ] **Step 4: Add built-in skill files**

Add one project-analysis skill and one document-summary skill using Deep Agents style `SKILL.md` folder layout.

- [ ] **Step 5: Run skills tests to verify they pass**

Run: `uv run pytest tests/test_skills.py -q`

Expected: all skills tests pass.

## Task 5: CLI and FastAPI Foundation

**Files:**
- Create: `src/easy_claw/api/__init__.py`
- Create: `src/easy_claw/api/main.py`
- Create: `src/easy_claw/cli.py`
- Create: `tests/test_api.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing API and CLI tests**

```python
from fastapi.testclient import TestClient

from easy_claw.api.main import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

```python
from typer.testing import CliRunner

from easy_claw.cli import app


def test_doctor_command_reports_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CLAW_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "easy-claw doctor" in result.stdout
```

- [ ] **Step 2: Run API and CLI tests to verify they fail**

Run: `uv run pytest tests/test_api.py tests/test_cli.py -q`

Expected: FAIL because API and CLI modules do not exist.

- [ ] **Step 3: Implement FastAPI app and Typer CLI**

Implement `/health`, `init-db`, `doctor`, `skills list`, `memory list`, and `serve`. Keep `chat` available but allow `--dry-run` so tests do not need a model.

- [ ] **Step 4: Run API and CLI tests to verify they pass**

Run: `uv run pytest tests/test_api.py tests/test_cli.py -q`

Expected: all tests pass.

## Task 6: Agent Runtime Adapter

**Files:**
- Create: `src/easy_claw/agent/__init__.py`
- Create: `src/easy_claw/agent/runtime.py`
- Create: `tests/test_agent_runtime.py`

- [ ] **Step 1: Write failing agent runtime tests**

```python
from easy_claw.agent.runtime import AgentRequest, FakeAgentRuntime


def test_fake_agent_runtime_returns_deterministic_result(tmp_path):
    runtime = FakeAgentRuntime()
    result = runtime.run(
        AgentRequest(
            prompt="hello",
            thread_id="thread-1",
            workspace_path=tmp_path,
            model=None,
            skills=[],
            memories=[],
        )
    )

    assert result.content == "easy-claw dry run: hello"
    assert result.thread_id == "thread-1"
```

- [ ] **Step 2: Run agent runtime tests to verify they fail**

Run: `uv run pytest tests/test_agent_runtime.py -q`

Expected: FAIL because agent runtime modules do not exist.

- [ ] **Step 3: Implement runtime dataclasses and fake runtime**

Add `AgentRequest`, `AgentResult`, `AgentRuntime`, and `FakeAgentRuntime`.

- [ ] **Step 4: Add lazy Deep Agents runtime class**

Add `DeepAgentsRuntime` with lazy imports. It should raise a clear `RuntimeError` if model config is missing. Live model calls are not covered by automated tests.

- [ ] **Step 5: Run agent runtime tests to verify they pass**

Run: `uv run pytest tests/test_agent_runtime.py -q`

Expected: agent runtime tests pass.

## Task 7: Windows Scripts

**Files:**
- Create: `scripts/start.ps1`
- Create: `scripts/doctor.ps1`

- [ ] **Step 1: Add script behavior**

`scripts/start.ps1` should check `uv`, run `uv sync`, run `uv run easy-claw init-db`, then start `uv run easy-claw serve`.

`scripts/doctor.ps1` should check `uv`, `git`, `pyproject.toml`, and print the matching `uv run easy-claw doctor` command.

- [ ] **Step 2: Run PowerShell parser checks**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $null = [scriptblock]::Create((Get-Content -Raw scripts/start.ps1)); $null = [scriptblock]::Create((Get-Content -Raw scripts/doctor.ps1)); 'ok' }"`

Expected: `ok`.

## Task 8: Full Verification

**Files:**
- Modify: none unless verification exposes failures.

- [ ] **Step 1: Run formatting**

Run: `uv run ruff format .`

Expected: formatting completes.

- [ ] **Step 2: Run lint**

Run: `uv run ruff check .`

Expected: no lint errors.

- [ ] **Step 3: Run tests**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 4: Run CLI smoke checks**

Run: `uv run easy-claw doctor`

Expected: prints doctor status and exits 0.

Run: `uv run easy-claw chat --dry-run "hello"`

Expected: prints `easy-claw dry run: hello` and exits 0.

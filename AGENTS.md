# AGENTS.md

This file is for coding agents that maintain `easy-claw`. Read it before editing code.

## Project Snapshot

`easy-claw` is a Windows-first local AI agent workbench. It provides:

- a Typer CLI and interactive terminal chat;
- a FastAPI local web/API server with a WebSocket chat endpoint;
- a LangChain `create_agent` runtime backed by LangGraph checkpoints;
- local tools for search, shell commands, Python snippets, document reading, file operations, browser automation, MCP tools, and Markdown skills;
- SQLite-backed session and audit metadata under `data/`.

The current package version is `0.5.0`. The repository uses a `src/` layout and `uv` for dependency management.

## First Checks

Before making changes:

```powershell
git status -sb
uv sync
```

Do not commit local runtime state or secrets. These are intentionally untracked:

- `.env`, `.env.*` except `.env.example`
- `mcp_servers.json`
- `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`
- `data/`, `runtime/`, `tmp/`, `.worktrees/`
- `.codex/`, `.workbuddy/`, editor directories

Use PowerShell examples in docs and scripts. This project is Windows-first.

## Required Commands

Run targeted tests while developing, then run the full checks before finishing:

```powershell
uv run pytest
uv run ruff check .
```

Formatting command:

```powershell
uv run ruff format .
```

Do not run `ruff format .` casually in a mixed worktree because it can touch unrelated files.

Useful app commands:

```powershell
uv run easy-claw --help
uv run easy-claw doctor
uv run easy-claw init-db
uv run easy-claw serve
uv run easy-claw dev skills list --all-sources
```

Startup scripts:

```powershell
.\scripts\start.ps1
.\scripts\start.ps1 -ApiServer
.\scripts\start.ps1 -Mcp
.\scripts\doctor.ps1
.\scripts\setup-mcp.ps1
```

`scripts/start.ps1` must work when called from outside the repo. It resolves the project root from `$PSScriptRoot`, changes to that root, checks for `uv`, checks native command exit codes, initializes the DB, and starts chat or API mode.

## Architecture Map

Core package: `src/easy_claw/`

- `config.py` loads `.env` and environment variables into `AppConfig`.
- `workspace.py` contains path normalization and workspace-relative path helpers.
- `skills.py` discovers Markdown `SKILL.md` directories and resolves skill source priority.
- `defaults.py` contains default model/tool call limits.
- `storage/db.py` creates the app SQLite schema.
- `storage/repositories.py` owns session and audit-log persistence.

Agent runtime:

- `agent/langchain_runtime.py` validates config, creates the chat model, builds tools, builds middleware, creates the LangChain agent, opens LangGraph SQLite checkpoints, and exposes `run()` / `stream()`.
- `agent/types.py` defines `ToolContext` and `ToolBundle`.
- `agent/toolset.py` composes core, file, browser, and MCP tool bundles.
- `agent/middleware.py` builds LangChain middleware: workspace file search, call limits, todo list, optional HITL, and summarization.
- `agent/approvals.py` implements console and static approval reviewers.
- `agent/streaming.py` converts LangGraph/LangChain stream items into `StreamEvent` records for CLI and WebSocket rendering.
- `agent/skill_tools.py` exposes `list_skills` and `read_skill` tools to the agent.
- `agent/prompts.py` builds the system prompt and injects skill summaries.

CLI:

- `cli/__init__.py` defines the Typer app, external commands, developer tools, session commands, and the `easy-claw` entrypoint.
- `cli/interactive.py` manages interactive chat, sessions, slash-command dispatch, streaming rendering, prompt-toolkit input, token usage, and conversation saving.
- `cli/slash.py` is the single registry for chat slash commands. Keep CLI and Web behavior aligned with this registry.
- `cli/views.py` renders Rich status, doctor, MCP, browser, skill, and session views.

API/Web:

- `api/app.py` creates the FastAPI app, static root, health endpoint, capability endpoints, session endpoints, and `/ws/chat`.
- `api/websocket.py` converts stream events to JSON and bridges blocking stream iteration into async WebSocket flow.
- `api/schemas.py` contains Pydantic request models.
- `api/static/index.html` is the current single-file web UI. It talks to `/ws/chat`, `/slash-commands`, `/sessions`, `/skills`, `/mcp`, and `/browser`.

Tools:

- `tools/core.py` exposes LangChain tools for web search, PowerShell commands, Python snippets, and document reading.
- `tools/files.py` wraps LangChain file-management tools and adds exact-string `edit_file`.
- `tools/mcp.py` reads `mcp_servers.json`, expands `${ENV_VAR}` references, tolerates failures in `auto` mode, prefixes MCP tools as `mcp__{server}__{tool}`, and wraps async-only tools for synchronous agent execution.
- `tools/browser.py` gates Playwright tools behind config and installed Chromium checks.
- `tools/search.py` chooses Tavily or DDGS based on config.
- `tools/documents.py` reads text files directly and converts supported document formats with MarkItDown.
- `tools/commands.py` runs PowerShell commands with timeout, output truncation, and exit-code propagation.
- `tools/python_runner.py` runs temporary Python snippets.

## Configuration

Config loading starts from `Path.cwd()` unless tests pass an explicit `cwd`. Startup scripts change to the repo root before running `uv`, so repo-local `.env` is used.

Important environment variables:

- `EASY_CLAW_MODEL`
- `EASY_CLAW_BASE_URL`
- `EASY_CLAW_API_KEY`, with `DEEPSEEK_API_KEY` fallback
- `EASY_CLAW_DATA_DIR`
- `EASY_CLAW_WORKSPACE`
- `EASY_CLAW_APPROVAL_MODE`: `permissive`, `balanced`, or `strict`
- `EASY_CLAW_EXECUTION_MODE`: currently `local`
- `EASY_CLAW_MAX_MODEL_CALLS`
- `EASY_CLAW_MAX_TOOL_CALLS`
- `EASY_CLAW_SEARCH_BACKEND`: `auto`, `ddgs`, or `tavily`
- `TAVILY_API_KEY`
- `EASY_CLAW_BROWSER_ENABLED`
- `EASY_CLAW_BROWSER_HEADLESS`
- `EASY_CLAW_MCP_ENABLED`: `auto`, `false`, or `true`
- `EASY_CLAW_MCP_CONFIG`
- `GITHUB_PERSONAL_ACCESS_TOKEN`
- `AMAP_MAPS_API_KEY`

Update `.env.example`, README, and tests together when changing config semantics.

## Data Model

Application DB path: `config.product_db_path`, default `data/easy-claw.db`.

Tables:

- `sessions`: id, title, workspace path, model, timestamps.
- `audit_logs`: event type, JSON payload, timestamp.

LangGraph checkpoints live separately at `config.checkpoint_db_path`, default `data/checkpoints.sqlite`.

Basic Memory data, when configured through MCP, lives under `data/basic-memory`.

## Skills

Skills are directories containing `SKILL.md`. Discovery order is low to high priority:

1. built-in repo skills under `<repo>/skills`;
2. user global legacy and agent paths under `%USERPROFILE%`;
3. project/workspace paths such as `.agents/skills`, `.easy-claw/skills`, and `skills`.

Later sources override earlier same-name skills. The agent initially receives only a summary and must call `read_skill` for matching skills.

Do not add `%USERPROFILE%\.codex\skills` to discovery by default; those skills can depend on Codex-specific tools that easy-claw does not provide.

## MCP

Default MCP setup is generated by `scripts/setup-mcp.ps1`.

Expected default services:

- `basic-memory` via `uvx basic-memory mcp --project easy-claw`
- `git` via `uvx mcp-server-git --repository <repo>`
- `github` when `GITHUB_PERSONAL_ACCESS_TOKEN` is set
- `amap-maps` when `AMAP_MAPS_API_KEY` is set and `npx` exists

`EASY_CLAW_MCP_ENABLED=auto` should remain forgiving: missing config, missing env vars, or failing individual services should not prevent startup. `enabled`/`true` should fail loudly.

## Testing Guide

Test layout mirrors source layout:

- `tests/agent/`: runtime, middleware, skill tools, tool bundle composition.
- `tests/api/`: FastAPI routes and WebSocket behavior.
- `tests/cli/`: Typer CLI, interactive loop, slash commands, views.
- `tests/core/`: config, package metadata, scripts, skills, structure.
- `tests/storage/`: repositories and DB behavior.
- `tests/tools/`: command, browser, document, file, MCP, Python, search tools.

Prefer focused tests for the module being changed. Use `tmp_path`, monkeypatches, fake agents/models, and `StaticApprovalReviewer` instead of hitting real model providers, browsers, MCP servers, or external APIs.

When changing:

- startup scripts: update `tests/core/test_scripts.py`;
- config parsing: update `tests/core/test_config.py` and `.env.example`;
- CLI slash commands: update `src/easy_claw/cli/slash.py`, README/docs, and CLI/API tests if Web depends on command specs;
- streaming events: update `tests/agent/test_runtime.py`, CLI rendering tests, and API WebSocket tests as needed;
- MCP behavior: update `tests/tools/test_mcp.py` and keep `mcp_servers.json.example` aligned;
- skill discovery: update `tests/core/test_skills.py`, `tests/agent/test_skill_tools.py`, and `docs/skills.md`.

## Documentation Guide

README is user-facing. Keep it focused on installation, configuration, startup, commands, feature scope, and links to deeper docs.

Detailed docs:

- `docs/architecture.md`: architecture and roadmap.
- `docs/cli.md`: slash commands and external CLI.
- `docs/development.md`: compact developer notes.
- `docs/skills.md`: skill format and discovery.
- `docs/superpowers/`: historical specs and plans.

This file, `AGENTS.md`, is the maintainer/AI coding guide. Keep it current when architecture, commands, config, or testing practices change.

## Coding Rules

- Preserve the `src/` layout.
- Keep changes scoped to the requested behavior.
- Avoid committing generated state.
- Prefer project patterns over new abstractions.
- Use `Path` and structured parsers for filesystem/config work.
- Keep Windows/PowerShell behavior explicit.
- Preserve UTF-8 output handling in scripts.
- For native PowerShell commands in scripts, check `$LASTEXITCODE`; `$ErrorActionPreference = "Stop"` is not enough for external executables.
- Keep tool errors user-readable in Chinese where the existing surface is Chinese.
- New risky tools should be included in `interrupt_on` so `balanced` and `strict` approval modes can pause before execution.
- Browser and MCP tools need cleanup callbacks when they hold resources.

## Known Current Limits

- Execution is local; there is no Docker/WSL sandbox implementation yet.
- Web approval flow is basic compared with terminal approval.
- MCP live health checks are limited; `doctor` mostly reports config/counts.
- Long-running task recovery beyond LangGraph checkpoints is still planned.
- The web UI is a single static HTML file served by FastAPI.


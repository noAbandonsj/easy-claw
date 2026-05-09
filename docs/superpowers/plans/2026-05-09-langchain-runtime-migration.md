# LangChain Runtime Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the DeepAgents runtime dependency with LangChain `create_agent` while preserving easy-claw chat, streaming, MCP, checkpoint, approval, and skills.

**Architecture:** Keep CLI, API, storage, MCP, and existing tool interfaces stable. Replace the agent construction layer and preserve easy-claw skills through LangChain tools. DeepAgents backend replacement file tools are explicitly deferred.

**Tech Stack:** Python 3.11+, LangChain `create_agent`, LangChain middleware, LangGraph `SqliteSaver`, LangChain Core tools, langchain-mcp-adapters, pytest, ruff.

---

## Decisions

- Implement on branch `codex/langchain-runtime-migration`.
- Do not implement `src/easy_claw/tools/files.py` in this migration.
- Keep legacy `.deepagents\skills` source discovery paths for user/project skill compatibility.
- Keep temporary compatibility aliases: `DeepAgentsRuntime` and `DeepAgentSession`.
- Remove `deepagents` from `pyproject.toml` and `uv.lock`.

## Tasks

- [x] Create branch and verify baseline with `uv run pytest` and `uv run ruff check .`.
- [x] Add neutral `AgentRuntime` and `AgentSession` protocols.
- [x] Rename runtime/session implementation to `LangChainAgentRuntime` and `LangChainAgentSession`.
- [x] Preserve temporary aliases for old runtime/session names.
- [x] Move approval into `HumanInTheLoopMiddleware(interrupt_on=...)`.
- [x] Replace `deepagents.create_deep_agent` with `langchain.agents.create_agent`.
- [x] Remove `skills=...`, `backend=...`, and direct `interrupt_on=...` from agent construction.
- [x] Add `list_skills` and `read_skill` LangChain tools.
- [x] Add skill summary guidance to the system prompt.
- [x] Remove unused DeepAgents backend helper code.
- [x] Update CLI/API imports to `LangChainAgentRuntime`.
- [x] Remove DeepAgents filesystem interrupt policy names for tools that no longer exist.
- [x] Remove `deepagents` dependency and update `uv.lock`.
- [x] Update README, architecture, and skills docs.

## Deferred Follow-Up

Open a separate plan for workspace file tools:

- `list_files`
- `read_text_file`
- `write_text_file`
- `edit_text_file`
- approval policy for write/edit
- tests for workspace escape prevention and exact replacement behavior

## Test Plan

Focused checks:

```powershell
uv run pytest tests/test_agent_runtime.py -q
uv run pytest tests/test_agent_middleware.py -q
uv run pytest tests/test_agent_toolset.py tests/test_skill_tools.py tests/test_skills.py -q
uv run pytest tests/test_api.py tests/test_cli.py -q
```

Full checks:

```powershell
uv run pytest
uv run ruff check .
uv run easy-claw doctor
uv run easy-claw dev skills list --all-sources
```

Optional smoke test when model credentials are configured:

```powershell
uv run easy-claw chat "总结 README.md 的主要内容"
```

## Acceptance Criteria

- No production code imports `deepagents`.
- `uv tree --depth 1` does not list `deepagents`.
- `uv.lock` has no `deepagents` package entry.
- LangChain runtime tests prove `create_agent` receives tools, middleware, system prompt, and checkpointer.
- Skill tool tests prove `list_skills`, `read_skill`, and project-priority override behavior.
- Full pytest and ruff checks pass.


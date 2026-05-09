# LangChain Runtime Migration Design

> Date: 2026-05-09
> Status: implemented in branch `codex/langchain-runtime-migration`
> Scope: replace the DeepAgents runtime dependency with LangChain `create_agent`; defer DeepAgents backend replacement file tools.

## Goal

Move easy-claw from `deepagents.create_deep_agent` to `langchain.agents.create_agent` while preserving the core user-facing behavior:

- CLI interactive chat and single-shot chat.
- WebSocket chat streaming.
- LangGraph SQLite checkpointing by `thread_id`.
- Streaming token, tool-call, tool-result, approval, error, and done events.
- Existing core tools: web search, PowerShell command execution, Python snippet execution, document reading.
- Browser tools when enabled.
- MCP tools through `langchain-mcp-adapters`.
- Basic Memory through the existing MCP configuration.
- easy-claw Markdown skills through a LangChain tool adapter.

## Deliberate Deferral

This migration does not implement replacement file tools for DeepAgents backend capabilities.

Deferred tools:

- `list_files`
- `read_text_file`
- `write_text_file`
- `edit_text_file`

Expected temporary behavior:

- The agent can still read supported documents through `read_document`.
- The agent can still use `run_command` and `run_python`.
- There is no dedicated workspace file edit tool in this migration.
- Follow-up work should add a focused `src/easy_claw/tools/files.py` implementation and approval policy.

## Runtime Mapping

| Previous DeepAgents feature | New LangChain/easy-claw behavior |
| --- | --- |
| `create_deep_agent(...)` | `langchain.agents.create_agent(...)` |
| `skills=[...]` | `list_skills` and `read_skill` LangChain tools plus prompt guidance |
| `backend=LocalShellBackend/CompositeBackend` | Deferred; no replacement file tools in this migration |
| direct `interrupt_on=...` argument | `HumanInTheLoopMiddleware(interrupt_on=...)` |
| `DeepAgentsRuntime` class name | `LangChainAgentRuntime`, with temporary compatibility alias |
| `DeepAgentSession` class name | `LangChainAgentSession`, with temporary compatibility alias |

## Implementation Shape

The runtime now constructs the agent roughly as:

```python
agent = create_agent(
    model=_build_chat_model(cfg.model, cfg.base_url, cfg.api_key),
    tools=[*tool_bundle.tools, *skill_tool_bundle.tools],
    system_prompt=system_prompt,
    middleware=build_agent_middleware(
        max_model_calls=cfg.max_model_calls,
        max_tool_calls=cfg.max_tool_calls,
        interrupt_on=interrupt_on,
    ),
    checkpointer=checkpointer,
)
```

`AgentRuntime` and `AgentSession` protocols provide neutral names for future runtime changes.

Compatibility aliases remain:

```python
DeepAgentsRuntime = LangChainAgentRuntime
DeepAgentSession = LangChainAgentSession
```

These aliases keep older tests and downstream imports from breaking immediately. They can be removed in a later cleanup.

## Skill Adapter

LangChain has no native `skills=` parameter. easy-claw preserves the existing skill directory format and exposes skills as tools:

- `list_skills()`: lists skill names, descriptions, source labels, and paths.
- `read_skill(name)`: reads the selected `SKILL.md` body and lists helper files beside it.

The system prompt tells the agent to call `read_skill` when a task clearly matches a skill.

Existing source paths remain supported, including legacy `.deepagents\skills` directories, because they are user/project skill storage locations rather than runtime dependencies.

## Approval

Approval policy still starts from `ToolBundle.interrupt_on`:

- `permissive`: no interrupts.
- `balanced` / `strict`: risky tool names are passed to `HumanInTheLoopMiddleware`.

The existing reviewer flow remains:

- `ConsoleApprovalReviewer`
- `StaticApprovalReviewer`
- `_invoke_with_approval`
- `_stream_with_approval`
- `Command(resume={"decisions": decisions})`

## Verification

Required checks:

```powershell
uv run pytest
uv run ruff check .
uv run easy-claw doctor
uv run easy-claw dev skills list --all-sources
```

Optional smoke test when API credentials are configured:

```powershell
uv run easy-claw chat "总结 README.md 的主要内容"
```

## Rollback

If the LangChain runtime fails, rollback is concentrated in:

- `src/easy_claw/agent/runtime.py`
- `src/easy_claw/agent/middleware.py`
- `src/easy_claw/agent/skill_tools.py`
- `pyproject.toml`
- `uv.lock`

Restore the previous `create_deep_agent` block and re-add `deepagents>=0.4.0` only if the new runtime cannot pass the focused runtime tests.


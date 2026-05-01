# easy-claw First Version Design

Date: 2026-05-01

## Decision

The first implementation uses the confirmed option A: CLI first, with a thin FastAPI foundation.

The goal is to run a usable Windows-first local agent workbench without building a custom agent framework. easy-claw should package, configure, constrain, and productize mature agent components. It should not duplicate LangChain or LangGraph runtime features.

## Scope

The first version includes:

- `uv` managed Python project with `pyproject.toml` and `uv.lock`.
- Typer CLI as the primary user entry.
- FastAPI app with basic health and session endpoints.
- SQLite local data directory.
- LangChain / LangGraph based agent runtime.
- SQLite checkpointer for short-term conversation state.
- Explicit product memory for user preferences and project notes.
- Workspace-bounded file and document tools.
- Markdown skill source, preferably backed by existing LangChain / Deep Agents skill support where practical.
- Developer-mode shell and Python tools only when explicitly enabled.
- Windows `scripts/start.ps1` and `scripts/doctor.ps1`.

The first version does not include:

- Full Web UI.
- Desktop app.
- Multi-user permissions.
- Plugin marketplace.
- Full MCP server management UI.
- Docker / WSL2 sandbox.
- Custom agent orchestration engine.

## Reuse Inventory

### Agent Runtime

Use the Deep Agents SDK as the first agent harness where it fits, because it already combines LangChain / LangGraph with skills, filesystem behavior, human-in-the-loop, and memory/checkpoint integration.

Keep a small `AgentRuntime` interface in easy-claw so the app is not locked to one harness. If Deep Agents cannot satisfy a Windows-first or workspace-bound requirement during implementation, the fallback is direct LangChain `create_agent`, which is also built on LangGraph and still avoids a custom runtime loop.

easy-claw owns only an `AgentRuntime` adapter:

- Build the model through LangChain-compatible model initialization.
- Register selected tools.
- Register middleware.
- Pass `thread_id` and runtime context.
- Return normalized events and final answers to CLI / API.

easy-claw does not reimplement planning, message routing, tool-call parsing, retry loops, or graph execution.

### Short-Term Memory and Conversation State

Use LangGraph checkpointing for short-term memory and resumable conversation state.

The first local backend should be `langgraph-checkpoint-sqlite>=3.0.1`. A GitHub advisory reports SQL injection in versions before 3.0.1 when untrusted metadata filter keys reach checkpoint history queries. easy-claw must not expose arbitrary checkpoint metadata filters through the API or CLI.

easy-claw should not create its own full message-history persistence layer for agent state. It may keep lightweight session metadata in product tables:

- session id
- title
- workspace path
- created and updated timestamps
- selected model
- selected skill names

Any UI-friendly tool-call list should be derived from LangGraph messages or emitted events, not treated as a second source of truth.

### Long-Term Product Memory

Keep long-term memory separate from LangGraph checkpoints.

Checkpoints answer: "What is the current graph state for this conversation?"

Product memory answers: "What should easy-claw remember across conversations?"

First-version product memory should be a small SQLite-backed repository for explicit items:

- user preferences
- project notes
- reusable task summaries

The agent can read selected product memories as context. It should only write product memories through explicit commands or clearly visible agent actions. This avoids hiding sensitive user data in an opaque memory layer.

Later versions can replace or augment this repository with LangGraph Store, Mem0, or Honcho.

### Human Approval

Use LangChain / LangGraph human-in-the-loop middleware where it fits, instead of building a custom approval engine.

The first version should classify tools into:

- `low`: read-only local context and safe summaries
- `confirm`: write output files, search network, run tests, execute shell
- `strong_confirm`: delete, overwrite, mass move, read secret-like paths, access system directories

CLI approval can be simple:

1. Show action type, command/path, working directory, workspace boundary, sandbox status, and reason.
2. Ask the user to allow or reject.
3. Resume the agent with the decision.

The risk policy is easy-claw product logic, but the pause/resume mechanics should use LangGraph / LangChain facilities where possible.

### Tools

Prefer existing LangChain tools and integrations.

Initial tools:

- Model: LangChain-compatible model initialization.
- File operations: LangChain file management tools or Deep Agents file-system tools, wrapped by an easy-claw workspace root policy.
- Document conversion: Microsoft MarkItDown for PDF, Word, PowerPoint, Excel, HTML, and similar files.
- Search: DuckDuckGo as the default no-key option; Tavily as optional configured enhancement.
- Shell: LangChain shell tool or middleware only in developer mode and only with approval.
- Python REPL: LangChain experimental Python REPL only in developer mode and only with approval.

easy-claw owns:

- workspace root selection
- path normalization for Windows
- risk classification
- developer-mode gating
- timeout and output limits
- CLI rendering

easy-claw does not own custom implementations of generic search, document parsing, or agent tool-call semantics.

### Skills

First-version skills are still Markdown files under:

```text
skills/
  core/
  user/
```

Before implementing a custom loader, check whether Deep Agents skill support can satisfy this requirement directly. If it can load Markdown skills with useful metadata and agent integration, use it.

If a thin local loader is still needed, keep it product-level and minimal:

- parse frontmatter
- list available skills
- provide selected skill text to the agent
- expose selected skills in CLI/API

It must not become a plugin framework.

### MCP

Do not implement a real MCP client in the first version.

When MCP is added, prefer `langchain-mcp-adapters` and expose MCP tools through the same tool registry and approval policy. The first version only needs a small `McpToolSource` protocol and directory structure that will not block later adoption.

### Storage

Use SQLite for product data:

- app settings
- workspaces
- session metadata
- explicit product memories
- risk action audit entries

Use LangGraph SQLite checkpointing for agent state.

These are intentionally separate. The checkpoint database is owned by LangGraph semantics; product tables are owned by easy-claw.

### API and CLI

The CLI is the primary first-version interface:

- `easy-claw chat`
- `easy-claw doctor`
- `easy-claw init-db`
- `easy-claw skills list`
- `easy-claw memory list`

FastAPI is intentionally thin:

- `GET /health`
- `GET /sessions`
- `POST /sessions`
- `GET /sessions/{id}`

It exists so later Web UI work can reuse the same local service instead of restructuring the project.

## Architecture

```text
CLI / FastAPI
  -> Config
  -> Storage repositories for product data
  -> AgentRuntime adapter
      -> Deep Agents SDK, fallback to LangChain create_agent
      -> LangGraph SQLite checkpointer
      -> selected model
      -> selected tools
      -> selected skills
      -> HITL middleware
  -> CLI/API result rendering
```

## Data Flow

1. User starts `easy-claw chat --workspace <path>`.
2. CLI loads config and creates or resumes a session.
3. CLI passes a `thread_id` to the agent runtime.
4. Agent runtime starts the Deep Agents based harness with the SQLite checkpointer. If Deep Agents cannot support a required first-version constraint, the same adapter starts LangChain `create_agent` directly.
5. Agent receives selected skills, product memories, and workspace-bounded tools.
6. Tool calls run through risk classification and approval middleware.
7. LangGraph checkpoint stores conversation state.
8. easy-claw product tables store only session metadata, explicit memory, settings, and risk audit entries.
9. CLI renders the final answer and relevant tool/action summaries.

## Error Handling

The first version should fail clearly:

- Missing `uv`: `start.ps1` and `doctor.ps1` show installation guidance.
- Missing model configuration: CLI explains which environment variable or config key is required.
- Missing optional dependency: CLI explains which feature needs it.
- Workspace outside allowed path: command fails before agent execution.
- Tool requires approval but no interactive terminal is available: command fails with a clear message.
- SQLite checkpoint or product DB cannot open: command reports the exact database path.

## Testing

Focused tests should cover:

- config loading defaults and overrides
- workspace path normalization and boundary checks
- product SQLite schema initialization
- session metadata repository
- product memory repository
- skills discovery behavior
- risk classification
- FastAPI `/health`
- CLI `doctor`

Agent tests should avoid live model calls by using fake or stub models where possible.

## Dependency Notes

Before pinning dependencies, confirm current package names and versions from official docs or package metadata:

- `langchain`
- `langgraph`
- `langgraph-checkpoint-sqlite>=3.0.1`
- `langchain-mcp-adapters`
- `deepagents`
- `fastapi`
- `uvicorn`
- `typer`
- `rich`
- `markitdown`
- `duckduckgo-search`

Use conservative version pins for packages with security-sensitive storage or tool-execution behavior. Do not allow user-controlled checkpoint metadata filter keys in first-version API routes.

## Implementation Decisions

- Prefer Deep Agents directly for skills and file-system behavior. Keep the `AgentRuntime` adapter fallback to direct LangChain `create_agent`.
- CLI chat requires live model configuration for real use. Tests and smoke checks use fake or stub models.
- `scripts/start.ps1` runs `uv sync`, initializes the database, and starts the thin FastAPI server. CLI commands remain available through `uv run easy-claw ...`.

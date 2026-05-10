# Development

This project uses a `src/` layout and keeps runtime state out of the tracked tree.

## Local Commands

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Source Layout

```text
src/easy_claw/
  agent/
    langchain_runtime.py  # LangChain agent creation and session lifecycle
    approvals.py          # human approval reviewers
    streaming.py          # StreamEvent conversion and usage extraction
    prompts.py            # system prompt construction
  api/
    app.py                # FastAPI app factory and routes
    schemas.py            # request/response models
    websocket.py          # WebSocket stream helpers
  cli/
    __init__.py           # Typer app and command entrypoint
    interactive.py        # interactive chat loop
    slash.py              # slash command registry and handlers
    views.py              # Rich rendering helpers
  storage/
  tools/
```

## Generated Files

The following directories are local state and should not be committed:

```text
.venv/
.pytest_cache/
.ruff_cache/
__pycache__/
data/
runtime/
.worktrees/
```

## Test Layout

Tests mirror the source areas so related behavior stays easy to find:

```text
tests/
  agent/
  api/
  cli/
  core/
  storage/
  tools/
```

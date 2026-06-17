# Development

This project uses a `src/` layout and keeps runtime state out of the tracked tree.

## Local Commands

```powershell
uv sync
Push-Location frontend
npm install
npm run test:run
npm run lint
npm run build
Pop-Location
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Web Frontend

The Web UI is a React + TypeScript + Vite app in `frontend/`. The FastAPI server
serves the production build from `frontend/dist/` at both `/` and `/app`.

Build the production Web UI before running the source checkout as a Web app:

```powershell
Push-Location frontend
npm install
npm run build
Pop-Location
uv run easy-claw serve
```

For frontend development, run the backend and Vite dev server in separate
terminals:

```powershell
uv run easy-claw serve
Push-Location frontend
npm run dev
Pop-Location
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
frontend/
  src/
    api/                 # REST and WebSocket client helpers
    components/          # React UI components
    hooks/               # browser runtime hooks
    state/               # pure reducers and command parsing
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
frontend/dist/
frontend/node_modules/
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

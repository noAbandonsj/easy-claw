# WebSocket Chat Frontend Design

## Goal

Add a web-based chat interface to easy-claw. The web UI reuses the existing REPL loop (`_run_interactive_loop`) via a WebSocket bridge, so CLI and web share identical behavior for all slash commands.

## Architecture

```
Browser (index.html) ←→ WebSocket ←→ FastAPI ←→ _run_interactive_loop (reused)
```

### IOCallback Protocol

Abstract I/O out of `_run_interactive_loop` so it works with both stdin/stdout (CLI) and WebSocket (web):

```python
class IOCallback(Protocol):
    def input(self) -> str: ...
    def output(self, text: str) -> None: ...
    def streaming_output(self) -> Callable[[str], None]: ...  # factory
```

- **CLI**: `ConsoleIOCallback` — `input()` / `console.print()` / token-by-token print
- **Web**: `WebSocketIOCallback` — `await ws.receive_text()` / `await ws.send_text()` / send token events as JSON

### Changed Functions

- `_run_interactive_loop` gains an optional `io: IOCallback` parameter (defaults to ConsoleIOCallback)
- All `console.print(...)` and `input()` calls inside the loop delegate to `io`
- `_render_streaming_turn` similarly gains an `io` parameter for token-by-token output

### New FastAPI Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ws/chat` | WebSocket | Bidirectional chat; one connection per browser tab |
| `/` | GET | Now serves `static/index.html` instead of JSON |
| `/health` | GET | Unchanged |
| `/sessions` | GET | Unchanged |
| `/sessions` | POST | Unchanged |
| `/sessions/{id}` | GET | Unchanged |

### WebSocket Protocol

**Server → Client** (JSON frames):
```json
{"type": "token", "content": "Hello"}
{"type": "tool_call_start", "tool_name": "search", "tool_args": "..."}
{"type": "tool_call_result", "tool_name": "search", "content": "..."}
{"type": "done", "usage": {"input": 100, "output": 200, "total": 300}}
{"type": "banner", "content": "easy-claw v0.4.0\nModel: ..."}
{"type": "command_output", "result": {...}}   // for /status, /help etc.
```

**Client → Server** (plain text frames):
```
hello world
/help
/clear
/status
```

### Frontend (single HTML file)

- `api/static/index.html` — one self-contained file
- Inline CSS, vanilla JS (no framework, no build step)
- Pink accent theme matching CLI styling
- Layout: header bar → message area → input box
- Streaming: renders tokens as they arrive via WebSocket messages
- Supports all slash commands identically to CLI

### Files Changed

| File | Change |
|------|--------|
| `src/easy_claw/cli.py` | Extract `IOCallback`, add to `_run_interactive_loop` and `_render_streaming_turn` |
| `src/easy_claw/api/main.py` | Add `/ws/chat` WebSocket, mount `/static`, redirect `/` to index.html |
| `src/easy_claw/api/static/index.html` | New frontend page |

## Non-Goals

- Multi-user support (single instance, single browser tab)
- Auth/login (developer tool, localhost only)
- Session history browsing in the web UI (use CLI `sessions` commands for that)
- Mobile responsive (desktop-first, may pinch-zoom)

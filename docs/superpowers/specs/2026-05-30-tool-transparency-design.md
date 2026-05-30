# Tool Transparency Design

## Goal

Enhance the existing Web chat workbench so users can understand tool activity at a glance:

- which tool the agent is calling;
- what kind of capability it belongs to;
- what the call is likely for;
- which key arguments were passed;
- what the result contains before opening the full output.

This is a workbench usability enhancement, not a runtime protocol change.

## Scope

The first implementation will enhance the current inline tool panels in the chat stream. It will not add a right-side inspector, a separate timeline drawer, or a new frontend framework.

Primary files:

- `src/easy_claw/api/static/app.js`
- `src/easy_claw/api/static/style.css`
- `src/easy_claw/api/static/index.html`, only if a small accessibility hook is needed
- `tests/api/test_api_app.py`

## Current Constraints

The WebSocket stream currently sends:

- `tool_call_start` with `tool_name` and `tool_args`;
- `tool_call_result` with `tool_name`, `content`, and `tool_result`.

It does not send a stable `tool_call_id`, explicit call reason, elapsed time, or result status metadata. Because of that, start and result cards will remain separate for now. The frontend will infer a plain-language explanation from the tool name and arguments.

## User Experience

### Tool Call Card

When a `tool_call_start` event arrives, the page renders an inline tool call card with:

- the original tool name;
- a category badge such as `搜索`, `文件`, `命令`, `Python`, `MCP`, `浏览器`, or `工具`;
- a status label for the call phase;
- a short Chinese explanation inferred from the tool name;
- a key argument summary;
- a collapsed details area with the full formatted arguments;
- a `复制参数` action.

The argument summary prioritizes fields that explain intent quickly:

- `query`, `q`, `search_query`
- `command`
- `path`, `file_path`, `filename`
- `url`
- `location`
- `code`

If no known field is present, the card shows a short first-level JSON summary.

### Tool Result Card

When a `tool_call_result` event arrives, the page renders an inline result card with:

- the original tool name;
- a result phase label;
- a short result summary;
- output length metadata;
- a collapsed full result area;
- a `复制结果` action.

Long summaries are truncated. Full content remains available in a scrollable monospace details region.

### Interaction

Tool cards default to summary-first display. Users can click the header or the expand button to show and hide full details.

Copy actions use `navigator.clipboard.writeText()`. Success and failure messages appear in the existing topbar status text, matching current Web UI behavior.

The implementation will continue using DOM APIs such as `createElement`, `textContent`, and event listeners. It will not reintroduce `innerHTML` or inline `onclick` handlers.

## Architecture

The frontend will add small helper functions in `app.js`:

- classify a tool name into a category and explanation;
- normalize arbitrary arguments/results into display strings;
- extract key argument summaries;
- build reusable tool card DOM nodes;
- copy formatted payloads to the clipboard.

The existing `handleMessage()` flow remains intact:

- `tool_call_start` calls the new card builder in call mode;
- `tool_call_result` calls the same card builder in result mode;
- topbar status updates continue to show the current phase.

The existing `formatContent()` helper may stay as the canonical formatter for complete details, or become a thin wrapper around the new formatter if that keeps duplication lower.

## Styling

`style.css` will evolve the existing `.tool-panel` styles rather than replacing the page theme. The card should feel consistent with the current dark workbench while being easier to scan:

- compact header with tool name and badges;
- muted explanation text under the title;
- summary rows for key arguments/results;
- explicit action buttons for expand/copy;
- scrollable details area for large JSON or text output.

The implementation should avoid nested decorative cards. A tool card can contain structured rows and a details block, but not multiple unrelated framed containers.

## Error Handling

Unknown tools receive the generic category `工具` and explanation `调用 agent 可用工具`.

Malformed or unserializable payloads fall back to `String(value)`.

Clipboard failure does not break the UI. It updates the topbar with a readable Chinese error message.

## Testing

Focused tests:

- update `tests/api/test_api_app.py` to verify split static assets still load;
- assert the JavaScript still avoids `innerHTML` and inline `onclick=`;
- assert the JavaScript contains the new tool transparency helper(s);
- assert the CSS contains the new tool card selectors.

Full verification before completion:

```powershell
uv run pytest tests/api/test_api_app.py
uv run pytest
uv run ruff check .
```

Manual verification with the local app:

```powershell
uv run easy-claw serve
```

Then open `http://127.0.0.1:8787/` and send a prompt that triggers a tool call. Confirm that the call card explains the tool, summarizes arguments, supports expansion, and copies details.

## Non-Goals

- No backend WebSocket protocol changes.
- No `tool_call_id` correlation.
- No elapsed-time tracking.
- No approval, cancellation, retry, or pause controls.
- No right-side inspector.
- No separate per-turn timeline drawer.
- No npm, framework, or build tooling.

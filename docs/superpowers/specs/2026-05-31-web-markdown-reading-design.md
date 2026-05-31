# Web Markdown Reading Design

## Goal

Enhance the local Web chat page so assistant replies are easier to read while they stream. The page will render assistant Markdown in real time, support safe limited HTML, improve code blocks, and add message-level actions without changing the existing dark neon visual identity.

This is a focused Web display enhancement. It does not change the agent runtime, FastAPI routes, WebSocket event schema, user-message rendering, or tool-card rendering.

## Scope

Primary files:

- `src/easy_claw/api/static/index.html`
- `src/easy_claw/api/static/app.js`
- `src/easy_claw/api/static/markdown.js`
- `src/easy_claw/api/static/style.css`
- `src/easy_claw/api/static/vendor/`
- `tests/api/test_api_app.py`
- `tests/api/test_web_markdown_smoke.py`

Assistant replies gain:

- real-time Markdown rendering during token streaming;
- common Markdown syntax support;
- sanitized limited raw HTML rendering;
- syntax-highlighted code blocks with language labels, copy actions, and long-code folding;
- a bottom action bar with `复制全文` and `查看源码`.

User messages and tool cards remain plain text.

## Dependency Strategy

The frontend remains vanilla HTML, CSS, and JavaScript with no npm installation or build step. Browser-ready library files are vendored under `/static/vendor/` so the local page continues to work offline:

- `marked.min.js`
- `purify.min.js`
- `highlight.min.js`
- `highlight-theme.css`

`index.html` loads the vendored scripts before `app.js` and loads the highlight stylesheet alongside the existing stylesheet.

Markdown display helpers live in `markdown.js`. The file exposes a browser global for `app.js`. It remains browser-ready JavaScript and does not introduce a bundler or Node.js requirement.

Vendored files must include their version and upstream license attribution in `src/easy_claw/api/static/vendor/LICENSES.md`.

The selected libraries have distinct responsibilities:

- `marked` parses Markdown into HTML;
- `DOMPurify` sanitizes parsed HTML before it reaches the DOM;
- `highlight.js` adds syntax highlighting to code blocks.

## Rendering Data Flow

Each assistant message keeps a source-of-truth raw Markdown string in frontend state.

When a WebSocket `token` event arrives:

1. append the token text to the current assistant message raw Markdown;
2. parse the complete current raw Markdown with `marked`;
3. sanitize the parsed HTML with `DOMPurify`;
4. render the sanitized HTML into the assistant message body;
5. normalize external links;
6. enhance code blocks without duplicating existing controls;
7. keep the streaming cursor visible.

Incomplete Markdown is expected during streaming. An unclosed code fence, table, or list may temporarily render as its current parseable form and settle naturally as more tokens arrive.

When a `done`, tool-call, or error event closes the current assistant segment, the cursor is removed while the rendered body and action bar remain.

## Message Structure

An assistant reply is a single message card with three stable regions:

1. rendered Markdown body;
2. optional raw-source view;
3. bottom action bar.

The bottom action bar is intentionally stable and visible instead of hover-only. It contains:

- `复制全文`: copy the original Markdown source;
- `查看源码`: switch between rendered Markdown and the raw Markdown source;
- `返回渲染`: replace `查看源码` while source mode is active.

The raw-source view uses a scrollable monospace block. It does not discard or recreate the underlying raw Markdown text.

## Supported Markdown

The first implementation supports the common reading set:

- headings;
- paragraphs;
- ordered and unordered lists;
- block quotes;
- links;
- inline code;
- fenced code blocks;
- tables;
- task lists.

Mermaid diagrams and mathematical notation are out of scope.

## Limited HTML Safety

Assistant Markdown may contain raw HTML, but HTML is never inserted into the page before sanitization.

Allowed content is limited to presentation-oriented elements needed for readable replies, including common text structure, lists, tables, links, code, and disclosure widgets such as `details` and `summary`.

The sanitizer removes dangerous content, including:

- `script`;
- `iframe`;
- `object`;
- `style`;
- `on*` event-handler attributes;
- dangerous URL schemes such as `javascript:`.

Links rendered from Markdown or allowed HTML are normalized after sanitization:

- external links open in a new tab;
- external links receive safe `rel` values such as `noopener noreferrer`;
- unsafe links remain removed or inert.

## Code Blocks

Each rendered fenced code block receives an idempotent enhancement wrapper:

- a compact toolbar;
- detected or declared language label;
- `复制代码`;
- syntax highlighting through `highlight.js`;
- long-code folding controls when the block exceeds approximately 18 lines or a fixed-height threshold.

Long code starts collapsed and exposes `展开代码` / `收起代码`.

During streaming, rerendering may recreate code nodes. The enhancement pass must tolerate repeated calls and avoid duplicate wrappers, toolbars, or buttons within the current DOM tree.

If highlighting fails, the code remains readable as plain escaped text.

## Styling

The existing dark neon theme remains intact. The enhancement refines typography and hierarchy within assistant cards:

- headings receive consistent spacing and restrained cyan emphasis;
- paragraphs and lists gain readable vertical rhythm;
- quotes use a muted left border;
- links are clearly distinguishable;
- inline code uses a compact contrasting background;
- tables have visible borders and horizontal scrolling on narrow screens;
- code blocks use a deeper background and compact toolbar;
- the bottom action bar uses low-emphasis buttons so it does not compete with the reply.

Mobile behavior:

- long code does not expand the page width;
- tables scroll horizontally inside the message body;
- action buttons wrap when needed;
- the assistant card stays readable alongside the existing sidebar.

## Failure Handling

The WebSocket chat flow must remain usable if a display enhancement fails:

- if Markdown parsing or sanitization throws, render the raw assistant text with `textContent`;
- if code highlighting throws, keep plain code text;
- if clipboard writing fails, report a readable Chinese message in the existing topbar status area;
- if a vendored library is unavailable, render readable plain-text assistant output instead of breaking token streaming.

The fallback path must not use unsanitized `innerHTML`.

## Testing

Extend `tests/api/test_api_app.py` to verify:

- each vendored asset is served by FastAPI static files;
- `index.html` loads the vendored scripts and highlight stylesheet;
- `app.js` includes Markdown rendering, sanitization, link normalization, code-block enhancement, copy, and source-toggle entry points;
- `style.css` includes Markdown body, message action bar, raw-source, table, and code-toolbar selectors;
- the frontend still avoids inline `onclick=` handlers.

Add focused Playwright smoke tests in `tests/api/test_web_markdown_smoke.py`. Match the existing opt-in browser-smoke convention: skip unless `EASY_CLAW_SMOKE_BROWSER=1` is set, because the Python dependency is installed by `uv sync` but the Chromium runtime remains an explicit local installation. In a real browser, cover:

- parser failure falls back to plain text;
- sanitized HTML removes executable content;
- external links receive safe attributes;
- code-block enhancement remains idempotent;
- long code starts collapsed;
- source toggle preserves raw Markdown.

Run:

```powershell
uv run pytest tests/api/test_api_app.py
uv run pytest
uv run ruff check .
```

Manual verification:

```powershell
uv run easy-claw serve
```

Open `http://127.0.0.1:8787/` and check:

- streaming headings, lists, quotes, tables, and task lists;
- allowed HTML rendering and dangerous HTML removal;
- language labels, syntax highlighting, code copy, and folding;
- full-message copy and source toggle;
- narrow-screen table and code behavior.

## Non-Goals

- No backend WebSocket protocol changes.
- No runtime, database, or session-history changes.
- No Markdown rendering for user messages.
- No Markdown rendering inside tool-card summaries or details.
- No Mermaid, mathematical notation, file previews, or rich attachments.
- No frontend framework, package manager, bundler, or build pipeline.

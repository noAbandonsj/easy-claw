# Tool Transparency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the Web chat inline tool panels so users can understand each tool call's category, likely purpose, key arguments, and result summary without changing the backend protocol.

**Architecture:** Keep the current split static assets and vanilla JavaScript. Add small display helper functions in `app.js`, replace the current `addToolPanel()` DOM builder with a summary-first tool card, and evolve existing `.tool-panel` styles in `style.css`. Backend routes and WebSocket event shapes stay unchanged.

**Tech Stack:** FastAPI static files, HTML/CSS, vanilla JavaScript DOM APIs, pytest, ruff.

---

## Scope Check

The approved spec covers one subsystem: Web UI rendering for tool call transparency. It does not require backend protocol changes, database changes, or runtime changes. This plan keeps implementation in the static frontend and the existing API static asset test.

## File Structure

- Modify `tests/api/test_api_app.py`: extend the existing split-static-assets regression test so it fails until the new JS helpers and CSS selectors exist.
- Modify `src/easy_claw/api/static/app.js`: add tool classification, payload summarization, clipboard, and reusable card builder helpers; route `tool_call_start` and `tool_call_result` through the new builder.
- Modify `src/easy_claw/api/static/style.css`: restyle `.tool-panel` internals to support badges, explanation text, summary rows, action buttons, and collapsed detail regions.
- Do not modify `src/easy_claw/api/app.py`, WebSocket schemas, or Python runtime code.

---

### Task 1: Add Static Asset Regression Tests

**Files:**
- Modify: `tests/api/test_api_app.py`

- [ ] **Step 1: Update the failing test**

Replace `test_web_ui_uses_split_static_assets()` with this complete function:

```python
def test_web_ui_uses_split_static_assets(tmp_path):
    client = TestClient(create_app(_test_config(tmp_path)))

    html = client.get("/").text

    assert '<link rel="stylesheet" href="/static/style.css">' in html
    assert '<script src="/static/app.js" defer></script>' in html
    assert "<style>" not in html
    assert "<script>" not in html

    css = client.get("/static/style.css")
    js = client.get("/static/app.js")
    assert css.status_code == 200
    assert "--bg-deep" in css.text
    assert ".tool-panel .tool-summary" in css.text
    assert ".tool-panel .tool-action" in css.text
    assert js.status_code == 200
    assert "function connect" in js.text
    assert "function describeTool" in js.text
    assert "function summarizeToolPayload" in js.text
    assert "function copyToolPayload" in js.text
    assert "innerHTML" not in js.text
    assert "onclick=" not in js.text
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected result:

```text
FAILED tests/api/test_api_app.py::test_web_ui_uses_split_static_assets
```

The failure should mention missing new CSS selectors or JavaScript helper names.

- [ ] **Step 3: Commit the failing test**

Run:

```powershell
git add tests/api/test_api_app.py
git commit -m "test: cover web tool transparency assets"
```

---

### Task 2: Add Tool Classification and Summary Helpers

**Files:**
- Modify: `src/easy_claw/api/static/app.js`

- [ ] **Step 1: Insert constants after the state variables**

Add this block after:

```javascript
let sessions = [];
```

Code:

```javascript
const TOOL_SUMMARY_KEYS = [
    'query',
    'q',
    'search_query',
    'command',
    'path',
    'file_path',
    'filename',
    'url',
    'location',
    'code',
];

const TOOL_DESCRIPTORS = [
    {
        keys: ['search', 'tavily', 'ddgs'],
        category: '搜索',
        explanation: '查找外部信息，用于补充或核对回答依据。',
    },
    {
        keys: ['read_document', 'document', 'markitdown'],
        category: '文档',
        explanation: '读取文档内容，提取可用于回答的文本。',
    },
    {
        keys: ['file', 'directory', 'read_', 'write_', 'edit_'],
        category: '文件',
        explanation: '读取或修改工作区文件。',
    },
    {
        keys: ['shell', 'command', 'powershell'],
        category: '命令',
        explanation: '执行本地 PowerShell 命令，查看或操作当前环境。',
    },
    {
        keys: ['python'],
        category: 'Python',
        explanation: '运行临时 Python 片段，处理计算或解析任务。',
    },
    {
        keys: ['browser', 'playwright'],
        category: '浏览器',
        explanation: '驱动浏览器页面，查看网页或执行页面操作。',
    },
    {
        keys: ['mcp__', 'mcp'],
        category: 'MCP',
        explanation: '调用 MCP 服务暴露的外部工具。',
    },
];
```

- [ ] **Step 2: Insert helper functions after `tableFromRows()`**

Add this complete helper block after `tableFromRows(rows)`:

```javascript
function normalizedToolName(name) {
    return name ? String(name) : '未知工具';
}

function describeTool(name) {
    const toolName = normalizedToolName(name);
    const lowered = toolName.toLowerCase();
    const descriptor = TOOL_DESCRIPTORS.find(item => item.keys.some(key => lowered.includes(key)));
    if (descriptor) {
        return {
            name: toolName,
            category: descriptor.category,
            explanation: descriptor.explanation,
        };
    }
    return {
        name: toolName,
        category: '工具',
        explanation: '调用 agent 可用工具。',
    };
}

function isPlainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function shortenText(text, limit = 180) {
    const normalized = String(text || '').replace(/\s+/g, ' ').trim();
    if (normalized.length <= limit) return normalized;
    return normalized.slice(0, limit - 1) + '…';
}

function previewValue(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return shortenText(value, 140);
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) return '[' + value.length + ' 项] ' + shortenText(formatContent(value), 120);
    if (isPlainObject(value)) return shortenText(formatContent(value), 120);
    return shortenText(String(value), 120);
}

function summarizeObjectFields(value, keys) {
    const rows = [];
    if (!isPlainObject(value)) return rows;
    keys.forEach(key => {
        if (Object.prototype.hasOwnProperty.call(value, key)) {
            rows.push([key, previewValue(value[key])]);
        }
    });
    return rows;
}

function summarizeFirstLevel(value) {
    if (!isPlainObject(value)) {
        const preview = previewValue(value);
        return preview ? [['内容', preview]] : [['内容', '空']];
    }
    const rows = Object.entries(value)
        .slice(0, 4)
        .map(([key, val]) => [key, previewValue(val)]);
    return rows.length ? rows : [['内容', '空对象']];
}

function summarizeToolPayload(value) {
    const rows = summarizeObjectFields(value, TOOL_SUMMARY_KEYS);
    return rows.length ? rows : summarizeFirstLevel(value);
}

function summarizeToolResult(value) {
    const formatted = formatContent(value);
    const lengthLabel = formatted.length.toLocaleString() + ' 字符';
    const preview = shortenText(formatted, 220);
    return [
        ['摘要', preview || '空结果'],
        ['长度', lengthLabel],
    ];
}
```

- [ ] **Step 3: Run the focused test and verify it still fails on CSS or missing copy helper**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected result:

```text
FAILED tests/api/test_api_app.py::test_web_ui_uses_split_static_assets
```

At this point the helper-name assertions for `describeTool` and `summarizeToolPayload` should pass. The remaining failure should be for `copyToolPayload` or CSS selectors.

- [ ] **Step 4: Commit the helper functions**

Run:

```powershell
git add src/easy_claw/api/static/app.js
git commit -m "feat: add web tool summary helpers"
```

---

### Task 3: Replace Tool Panel Rendering with Summary-First Cards

**Files:**
- Modify: `src/easy_claw/api/static/app.js`

- [ ] **Step 1: Replace `addToolPanel()`, `togglePanel()`, and `formatContent()`**

Replace the existing `addToolPanel(kind, name, content)`, `togglePanel(panel)`, and `formatContent(val)` functions with this complete block:

```javascript
function addToolPanel(kind, name, content) {
    const panelKind = kind === 'result' ? 'result' : 'call';
    const panel = el('div', { className: 'tool-panel ' + panelKind });
    const descriptor = describeTool(name);
    const formatted = formatContent(content);
    const summaryRows = panelKind === 'result'
        ? summarizeToolResult(content)
        : summarizeToolPayload(content);

    const header = el('button', { className: 'header ' + panelKind });
    header.type = 'button';

    const title = el('span', { className: 'tool-title-block' });
    const meta = el('span', { className: 'tool-meta' });
    meta.append(
        el('span', { className: 'tool-badge', text: descriptor.category }),
        el('span', {
            className: 'tool-phase',
            text: panelKind === 'result' ? '结果' : '调用',
        }),
    );
    title.append(
        meta,
        el('span', { className: 'tool-name', text: descriptor.name }),
        el('span', { className: 'tool-explanation', text: descriptor.explanation }),
    );

    header.append(title, el('span', { className: 'arrow', text: '\u25b6' }));
    header.addEventListener('click', () => togglePanel(panel));

    const summary = el('div', { className: 'tool-summary' });
    summaryRows.forEach(([label, value]) => {
        const row = el('div', { className: 'tool-summary-row' });
        row.append(
            el('span', { className: 'tool-summary-key', text: label }),
            el('span', { className: 'tool-summary-value', text: value }),
        );
        summary.append(row);
    });

    const actions = el('div', { className: 'tool-actions' });
    const expandButton = el('button', { className: 'tool-action tool-expand', text: '展开详情' });
    expandButton.type = 'button';
    expandButton.addEventListener('click', () => togglePanel(panel));

    const copyLabel = panelKind === 'result' ? '复制结果' : '复制参数';
    const copyButton = el('button', { className: 'tool-action', text: copyLabel });
    copyButton.type = 'button';
    copyButton.addEventListener('click', () => copyToolPayload(copyLabel, formatted));
    actions.append(expandButton, copyButton);

    panel.append(
        header,
        summary,
        actions,
        el('div', { className: 'body', text: formatted }),
    );
    msgEl.appendChild(panel);
}

function togglePanel(panel) {
    panel.classList.toggle('open');
    const expandButton = panel.querySelector('.tool-expand');
    if (expandButton) {
        expandButton.textContent = panel.classList.contains('open') ? '收起详情' : '展开详情';
    }
}

async function copyToolPayload(label, content) {
    try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
            throw new Error('浏览器不支持剪贴板写入');
        }
        await navigator.clipboard.writeText(content);
        topbarStatus.textContent = label + '已复制';
    } catch (e) {
        topbarStatus.textContent = label + '失败：' + (e.message || '无法写入剪贴板');
    }
}

function formatContent(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    try { return JSON.stringify(val, null, 2); } catch (e) { return String(val); }
}
```

- [ ] **Step 2: Verify the JavaScript contract still avoids unsafe DOM patterns**

Run:

```powershell
Select-String -Path src\easy_claw\api\static\app.js -Pattern "innerHTML|onclick="
```

Expected result:

```text
```

No matches should be printed.

- [ ] **Step 3: Run the focused test and verify it still fails only on CSS selectors**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected result:

```text
FAILED tests/api/test_api_app.py::test_web_ui_uses_split_static_assets
```

The remaining failure should be for `.tool-panel .tool-summary` or `.tool-panel .tool-action`.

- [ ] **Step 4: Commit the rendering change**

Run:

```powershell
git add src/easy_claw/api/static/app.js
git commit -m "feat: render explanatory web tool cards"
```

---

### Task 4: Style Tool Transparency Cards

**Files:**
- Modify: `src/easy_claw/api/static/style.css`

- [ ] **Step 1: Replace the existing tool panel CSS block**

Replace the block from `.tool-panel {` through `.tool-panel.open .arrow { transform: rotate(90deg); }` with:

```css
.tool-panel {
    align-self: stretch;
    border: 1px solid #00ffff30;
    border-radius: 8px;
    overflow: hidden;
    margin: 4px 0;
    background: rgba(18, 18, 42, 0.55);
    box-shadow: 0 0 8px #00ffff10;
    animation: msg-in 0.2s ease-out;
}
.tool-panel.result {
    border-color: #3fb95030;
    box-shadow: 0 0 8px #3fb95010;
}
.tool-panel .header {
    width: 100%;
    padding: 8px 12px;
    border: 0;
    font-family: inherit;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    user-select: none;
    text-align: left;
}
.tool-panel .header.call { background: #00ffff08; color: var(--cyan-dim); }
.tool-panel .header.result { background: #3fb95008; color: var(--green); }
.tool-panel .tool-title-block {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.tool-panel .tool-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
}
.tool-panel .tool-badge,
.tool-panel .tool-phase {
    display: inline-flex;
    align-items: center;
    min-height: 18px;
    padding: 1px 6px;
    border-radius: 999px;
    font-size: 10px;
    line-height: 1.4;
}
.tool-panel .tool-badge {
    color: var(--cyan-dim);
    background: #00ffff12;
    border: 1px solid #00ffff20;
}
.tool-panel.result .tool-badge {
    color: var(--green);
    background: #3fb95012;
    border-color: #3fb95020;
}
.tool-panel .tool-phase {
    color: var(--dim);
    background: #ffffff08;
}
.tool-panel .tool-name {
    color: var(--text);
    overflow-wrap: anywhere;
}
.tool-panel .tool-explanation {
    color: var(--dim);
    font-size: 11px;
    font-weight: 400;
    line-height: 1.35;
}
.tool-panel .tool-summary {
    padding: 8px 12px 0;
    display: grid;
    gap: 5px;
}
.tool-panel .tool-summary-row {
    display: grid;
    grid-template-columns: minmax(68px, 120px) 1fr;
    gap: 8px;
    font-size: 12px;
    line-height: 1.4;
}
.tool-panel .tool-summary-key {
    color: var(--cyan-dim);
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
    overflow-wrap: anywhere;
}
.tool-panel.result .tool-summary-key { color: var(--green); }
.tool-panel .tool-summary-value {
    color: var(--text);
    overflow-wrap: anywhere;
}
.tool-panel .tool-actions {
    padding: 8px 12px 10px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}
.tool-panel .tool-action {
    background: #ffffff08;
    color: var(--text);
    border: 1px solid #ffffff14;
    border-radius: 6px;
    padding: 5px 9px;
    font-family: inherit;
    font-size: 11px;
    line-height: 1.2;
    cursor: pointer;
}
.tool-panel .tool-action:hover {
    border-color: #00ffff30;
    color: var(--cyan-dim);
}
.tool-panel.result .tool-action:hover {
    border-color: #3fb95030;
    color: var(--green);
}
.tool-panel .body {
    padding: 8px 12px;
    font-size: 13px;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
    background: rgba(0, 0, 0, 0.25);
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    display: none;
}
.tool-panel.open .body { display: block; }
.tool-panel .arrow {
    flex-shrink: 0;
    transition: transform 0.2s;
}
.tool-panel.open .arrow { transform: rotate(90deg); }
```

- [ ] **Step 2: Run the focused static asset test and verify it passes**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected result:

```text
1 passed
```

- [ ] **Step 3: Run all API tests**

Run:

```powershell
uv run pytest tests/api/test_api_app.py -q
```

Expected result:

```text
11 passed
```

If the test file has changed before execution, the pass count may differ, but every test in `tests/api/test_api_app.py` must pass.

- [ ] **Step 4: Commit the CSS change**

Run:

```powershell
git add src/easy_claw/api/static/style.css
git commit -m "style: improve web tool card readability"
```

---

### Task 5: Verify Full Project and Manual Web Behavior

**Files:**
- No code edits expected.

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
uv run pytest
```

Expected result:

```text
passed
```

All tests must pass. If unrelated existing failures appear, capture the exact failing tests and inspect whether they were caused by the static asset changes before proceeding.

- [ ] **Step 2: Run ruff**

Run:

```powershell
uv run ruff check .
```

Expected result:

```text
All checks passed!
```

- [ ] **Step 3: Start the local Web app**

Run:

```powershell
uv run easy-claw serve
```

Expected result:

```text
Uvicorn running on http://127.0.0.1:8787
```

Keep the process running while manually checking the browser.

- [ ] **Step 4: Manually verify the Web UI**

Open:

```text
http://127.0.0.1:8787/
```

Send a prompt likely to trigger a tool call, such as:

```text
读取 README.md 并总结项目启动方式
```

Verify these behaviors:

- a tool call card appears inline in the chat stream;
- the card shows a category badge, tool name, and Chinese explanation;
- the card shows key argument rows;
- the full details are collapsed by default;
- clicking the header or `展开详情` opens the full details;
- `复制参数` or `复制结果` updates the topbar status;
- assistant token streaming still works after the tool card.

- [ ] **Step 5: Stop the local server**

Stop the foreground `uv run easy-claw serve` process with `Ctrl+C`.

Expected result:

```text
Application shutdown complete
```

- [ ] **Step 6: Commit final verification note if any files changed**

If no files changed during manual verification, do not create a commit. If a small fix was needed, commit only that fix:

```powershell
git add src/easy_claw/api/static/app.js src/easy_claw/api/static/style.css tests/api/test_api_app.py
git commit -m "fix: polish web tool transparency cards"
```

---

## Self-Review

Spec coverage:

- Tool category, explanation, key arguments, result summary: covered by Tasks 2 and 3.
- Summary-first collapsed details: covered by Tasks 3 and 4.
- Copy actions: covered by Task 3.
- No backend protocol changes: preserved by file structure and all tasks.
- Static tests and full verification: covered by Tasks 1, 4, and 5.

Placeholder scan:

- No placeholder markers or unspecified implementation steps are present.
- Each code-changing step includes exact code or an exact replacement block.

Type and name consistency:

- Test assertions use `describeTool`, `summarizeToolPayload`, and `copyToolPayload`.
- Task 2 defines `describeTool` and `summarizeToolPayload`.
- Task 3 defines `copyToolPayload` and uses the existing `formatContent` API.
- CSS selectors asserted in Task 1 are defined in Task 4.

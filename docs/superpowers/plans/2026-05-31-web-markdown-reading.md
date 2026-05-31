# Web Markdown Reading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render assistant replies as safe real-time Markdown in the local Web chat page, with offline vendored dependencies, readable code blocks, and message-level copy/source actions.

**Architecture:** Keep the current FastAPI static-file routes and WebSocket protocol unchanged. Add a browser-only `markdown.js` helper responsible for parse, sanitize, link normalization, code-block enhancement, and source-mode toggling; keep `app.js` responsible for WebSocket state, message construction, and topbar feedback. Vendor pinned browser-ready builds so the local Web page remains offline-capable and does not require npm or a build step.

**Tech Stack:** FastAPI static files, vanilla HTML/CSS/JavaScript, Marked `18.0.4`, DOMPurify `3.4.7`, highlight.js `11.11.1`, pytest, Playwright smoke tests, Ruff.

---

## File Map

| File | Responsibility |
|---|---|
| `src/easy_claw/api/static/index.html` | Load vendored styles and scripts in dependency order. |
| `src/easy_claw/api/static/vendor/marked.min.js` | Vendored Marked UMD build. |
| `src/easy_claw/api/static/vendor/purify.min.js` | Vendored DOMPurify browser build. |
| `src/easy_claw/api/static/vendor/highlight.min.js` | Vendored highlight.js browser build. |
| `src/easy_claw/api/static/vendor/highlight-theme.css` | Vendored highlight.js dark theme. |
| `src/easy_claw/api/static/vendor/LICENSES.md` | Versions, upstream licenses, source URLs, and checksums for vendored files. |
| `src/easy_claw/api/static/markdown.js` | Parse, sanitize, render, normalize links, enhance code blocks, and toggle source mode. |
| `src/easy_claw/api/static/app.js` | Construct assistant message cards and integrate `markdown.js` with streaming events. |
| `src/easy_claw/api/static/style.css` | Typography, code toolbar, source view, action bar, and mobile presentation. |
| `tests/api/test_api_app.py` | Default static integration contract, runnable without Chromium. |
| `tests/api/test_web_markdown_smoke.py` | Opt-in real-browser behavior checks under `EASY_CLAW_SMOKE_BROWSER=1`. |
| `README.md` | User-facing Web-page capability note. |
| `docs/architecture.md` | Static frontend responsibility map. |
| `AGENTS.md` | Maintainer map for the split Web frontend. |

## Task 1: Vendor Offline Browser Dependencies

**Files:**
- Modify: `tests/api/test_api_app.py`
- Modify: `src/easy_claw/api/static/index.html`
- Create: `src/easy_claw/api/static/vendor/marked.min.js`
- Create: `src/easy_claw/api/static/vendor/purify.min.js`
- Create: `src/easy_claw/api/static/vendor/highlight.min.js`
- Create: `src/easy_claw/api/static/vendor/highlight-theme.css`
- Create: `src/easy_claw/api/static/vendor/LICENSES.md`

- [ ] **Step 1: Extend the static-asset regression test before adding files**

Replace `test_web_ui_uses_split_static_assets()` in `tests/api/test_api_app.py` with:

```python
def test_web_ui_uses_split_static_assets(tmp_path):
    client = TestClient(create_app(_test_config(tmp_path)))

    html = client.get("/").text

    assert '<link rel="stylesheet" href="/static/vendor/highlight-theme.css">' in html
    assert '<link rel="stylesheet" href="/static/style.css">' in html
    assert '<script src="/static/vendor/marked.min.js" defer></script>' in html
    assert '<script src="/static/vendor/purify.min.js" defer></script>' in html
    assert '<script src="/static/vendor/highlight.min.js" defer></script>' in html
    assert '<script src="/static/markdown.js" defer></script>' in html
    assert '<script src="/static/app.js" defer></script>' in html
    assert "<style>" not in html
    assert "<script>" not in html

    vendor_paths = [
        "/static/vendor/marked.min.js",
        "/static/vendor/purify.min.js",
        "/static/vendor/highlight.min.js",
        "/static/vendor/highlight-theme.css",
        "/static/vendor/LICENSES.md",
    ]
    for path in vendor_paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text, path

    css = client.get("/static/style.css")
    markdown_js = client.get("/static/markdown.js")
    app_js = client.get("/static/app.js")
    assert css.status_code == 200
    assert "--bg-deep" in css.text
    assert ".tool-panel .tool-summary" in css.text
    assert ".tool-panel .tool-action" in css.text
    assert "@media (max-width: 640px)" in css.text
    assert markdown_js.status_code == 200
    assert app_js.status_code == 200
    assert "function connect" in app_js.text
    assert "function describeTool" in app_js.text
    assert "function summarizeToolPayload" in app_js.text
    assert "function copyToolPayload" in app_js.text
    assert "label + '失败：无法写入剪贴板'" in app_js.text
    assert "innerHTML" not in app_js.text
    assert "onclick=" not in app_js.text
```

- [ ] **Step 2: Run the focused test and verify the new contract fails**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected: `FAIL` because the vendor links and `/static/markdown.js` do not exist yet.

- [ ] **Step 3: Download pinned browser builds into the static vendor directory**

Run:

```powershell
$vendor = "src\easy_claw\api\static\vendor"
New-Item -ItemType Directory -Force $vendor | Out-Null
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/marked@18.0.4/lib/marked.umd.min.js" -OutFile "$vendor\marked.min.js"
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/dompurify@3.4.7/dist/purify.min.js" -OutFile "$vendor\purify.min.js"
Invoke-WebRequest "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js" -OutFile "$vendor\highlight.min.js"
Invoke-WebRequest "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github-dark.min.css" -OutFile "$vendor\highlight-theme.css"
```

Verify checksums:

```powershell
$expected = @{
    "highlight-theme.css" = "9F208D022102B1D0C7AEBFECD8E42CA7997D5DE636649D2B31EA63093D809019"
    "highlight.min.js" = "C4A399DD6F488BC97A3546E3476747B3E714C99C57B9473154C6FB8D259B9381"
    "marked.min.js" = "93ACCD6F8A62962FDD8053385EDEF60840993A1C61CA58A57D6F632C4B9A581D"
    "purify.min.js" = "F84E522876A6CFADECB89C173356409ACEC39F580C69018559C9A50E96299B0C"
}
Get-ChildItem $vendor -File | Where-Object Name -ne "LICENSES.md" | ForEach-Object {
    $actual = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    if ($actual -ne $expected[$_.Name]) {
        throw "Checksum mismatch for $($_.Name): $actual"
    }
}
```

Expected: no output and exit code `0`.

- [ ] **Step 4: Add the vendor attribution file**

Create `src/easy_claw/api/static/vendor/LICENSES.md`:

```markdown
# Vendored Browser Assets

These browser-ready files are committed so the local Web UI remains usable offline.

| Local file | Upstream package | Version | License | Download source |
|---|---|---|---|---|
| `marked.min.js` | [marked](https://github.com/markedjs/marked) | `18.0.4` | [MIT](https://github.com/markedjs/marked/blob/v18.0.4/LICENSE) | `https://cdn.jsdelivr.net/npm/marked@18.0.4/lib/marked.umd.min.js` |
| `purify.min.js` | [DOMPurify](https://github.com/cure53/DOMPurify) | `3.4.7` | [MPL-2.0 OR Apache-2.0](https://github.com/cure53/DOMPurify/blob/3.4.7/LICENSE) | `https://cdn.jsdelivr.net/npm/dompurify@3.4.7/dist/purify.min.js` |
| `highlight.min.js` | [highlight.js CDN release](https://github.com/highlightjs/cdn-release) | `11.11.1` | [BSD-3-Clause](https://github.com/highlightjs/highlight.js/blob/11.11.1/LICENSE) | `https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js` |
| `highlight-theme.css` | [highlight.js CDN release](https://github.com/highlightjs/cdn-release) | `11.11.1` | [BSD-3-Clause](https://github.com/highlightjs/highlight.js/blob/11.11.1/LICENSE) | `https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github-dark.min.css` |

## SHA-256

| Local file | SHA-256 |
|---|---|
| `marked.min.js` | `93ACCD6F8A62962FDD8053385EDEF60840993A1C61CA58A57D6F632C4B9A581D` |
| `purify.min.js` | `F84E522876A6CFADECB89C173356409ACEC39F580C69018559C9A50E96299B0C` |
| `highlight.min.js` | `C4A399DD6F488BC97A3546E3476747B3E714C99C57B9473154C6FB8D259B9381` |
| `highlight-theme.css` | `9F208D022102B1D0C7AEBFECD8E42CA7997D5DE636649D2B31EA63093D809019` |
```

- [ ] **Step 5: Load dependencies before application code**

Replace the stylesheet block in `src/easy_claw/api/static/index.html` with:

```html
<link rel="stylesheet" href="/static/vendor/highlight-theme.css">
<link rel="stylesheet" href="/static/style.css">
```

Replace the script block at the bottom with:

```html
<script src="/static/vendor/marked.min.js" defer></script>
<script src="/static/vendor/purify.min.js" defer></script>
<script src="/static/vendor/highlight.min.js" defer></script>
<script src="/static/markdown.js" defer></script>
<script src="/static/app.js" defer></script>
```

- [ ] **Step 6: Add a temporary empty helper so the static path exists**

Create `src/easy_claw/api/static/markdown.js`:

```javascript
window.EasyClawMarkdown = {};
```

- [ ] **Step 7: Run the focused test and verify the asset contract passes**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected: `1 passed`.

- [ ] **Step 8: Commit the vendored assets and dependency loading**

Run:

```powershell
git add src/easy_claw/api/static/index.html src/easy_claw/api/static/markdown.js src/easy_claw/api/static/vendor tests/api/test_api_app.py
git commit -m "feat: vendor offline web markdown dependencies"
```

## Task 2: Build the Safe Markdown Rendering Helper

**Files:**
- Modify: `tests/api/test_api_app.py`
- Create: `tests/api/test_web_markdown_smoke.py`
- Modify: `src/easy_claw/api/static/markdown.js`

- [ ] **Step 1: Add opt-in browser behavior tests before implementing the helper**

Create `tests/api/test_web_markdown_smoke.py`:

```python
"""Real browser checks for Web Markdown rendering.

Requires ``uv run playwright install chromium`` and ``EASY_CLAW_SMOKE_BROWSER=1``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

playwright_installed = os.environ.get("EASY_CLAW_SMOKE_BROWSER", "").lower() in (
    "1",
    "true",
    "yes",
)

pytestmark = pytest.mark.skipif(
    not playwright_installed,
    reason="Set EASY_CLAW_SMOKE_BROWSER=1 to run real Playwright tests",
)

_STATIC_DIR = Path(__file__).parents[2] / "src" / "easy_claw" / "api" / "static"


@pytest.fixture
def markdown_page() -> Iterator[Page]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<div id="target"></div>')
        for script in (
            "vendor/marked.min.js",
            "vendor/purify.min.js",
            "vendor/highlight.min.js",
            "markdown.js",
        ):
            page.add_script_tag(path=str(_STATIC_DIR / script))
        yield page
        browser.close()


def test_render_into_sanitizes_html_and_normalizes_external_links(markdown_page: Page):
    source = """
# 标题

<a href="https://example.com/docs" onclick="window.hacked = true">外链</a>
<a href="javascript:alert(1)">危险链接</a>
<script>window.hacked = true</script>
<details open><summary>展开</summary>正文</details>
"""

    rendered = markdown_page.evaluate(
        """source => {
            const target = document.querySelector("#target");
            return EasyClawMarkdown.renderInto(target, source);
        }""",
        source,
    )

    target = markdown_page.locator("#target")
    assert rendered is True
    assert target.locator("h1").inner_text() == "标题"
    assert target.locator("script").count() == 0
    assert target.locator("[onclick]").count() == 0
    assert target.locator("details").count() == 1
    assert target.locator("a").nth(0).get_attribute("target") == "_blank"
    assert target.locator("a").nth(0).get_attribute("rel") == "noopener noreferrer"
    assert target.locator("a").nth(1).get_attribute("href") is None


def test_render_into_enhances_long_code_once_and_copies_source(markdown_page: Page):
    source = "```python\n" + "\n".join(f"print({index})" for index in range(24)) + "\n```"

    markdown_page.evaluate(
        """source => {
            window.copiedCode = null;
            const target = document.querySelector("#target");
            const options = {
                onCopy: (label, text) => {
                    window.copiedCode = {label, text};
                },
            };
            EasyClawMarkdown.renderInto(target, source, options);
            EasyClawMarkdown.enhanceCodeBlocks(target, options);
        }""",
        source,
    )

    target = markdown_page.locator("#target")
    assert target.locator(".md-code-shell").count() == 1
    assert target.locator(".md-code-shell.collapsed").count() == 1
    assert target.locator(".md-code-language").inner_text() == "python"
    assert target.locator("code.hljs").count() == 1

    target.locator(".md-code-copy").click()
    copied = markdown_page.evaluate("window.copiedCode")
    assert copied["label"] == "复制代码"
    assert "print(23)" in copied["text"]


def test_render_into_falls_back_to_plain_text_when_parser_throws(markdown_page: Page):
    source = "<b>保持为文本</b>"

    result = markdown_page.evaluate(
        """source => {
            const target = document.querySelector("#target");
            const parse = window.marked.parse;
            window.marked.parse = () => {
                throw new Error("parse failed");
            };
            const rendered = EasyClawMarkdown.renderInto(target, source);
            window.marked.parse = parse;
            return {rendered, text: target.textContent, html: target.innerHTML};
        }""",
        source,
    )

    assert result == {
        "rendered": False,
        "text": source,
        "html": "&lt;b&gt;保持为文本&lt;/b&gt;",
    }


def test_toggle_source_mode_preserves_raw_markdown(markdown_page: Page):
    source = "# 标题\n\n`code`"

    result = markdown_page.evaluate(
        """source => {
            document.body.insertAdjacentHTML("beforeend", `
                <div class="message assistant" id="message">
                    <div class="markdown-body">渲染结果</div>
                    <pre class="assistant-source" hidden></pre>
                    <button class="assistant-source-toggle" type="button">查看源码</button>
                </div>
            `);
            const message = document.querySelector("#message");
            const shown = EasyClawMarkdown.toggleSourceMode(message, source);
            const sourceText = message.querySelector(".assistant-source").textContent;
            const buttonText = message.querySelector(".assistant-source-toggle").textContent;
            const hidden = message.querySelector(".markdown-body").hidden;
            EasyClawMarkdown.toggleSourceMode(message, source);
            return {shown, sourceText, buttonText, hidden};
        }""",
        source,
    )

    assert result == {
        "shown": True,
        "sourceText": source,
        "buttonText": "返回渲染",
        "hidden": True,
    }
```

- [ ] **Step 2: Install Chromium only if the local smoke runtime is missing**

Run:

```powershell
uv run playwright install chromium
```

Expected: Chromium is present after the command finishes.

- [ ] **Step 3: Run the smoke tests and verify the helper behavior is missing**

Run:

```powershell
$env:EASY_CLAW_SMOKE_BROWSER = "1"
uv run pytest tests/api/test_web_markdown_smoke.py -q
```

Expected: `FAIL` because the temporary `EasyClawMarkdown` object does not define `renderInto`, `enhanceCodeBlocks`, or `toggleSourceMode`.

- [ ] **Step 4: Replace the temporary helper with the complete safe renderer**

Replace `src/easy_claw/api/static/markdown.js` with:

```javascript
(function (global) {
    'use strict';

    const FORBID_TAGS = ['script', 'iframe', 'object', 'style'];
    const FORBID_ATTR = ['style'];
    const LONG_CODE_LINES = 18;
    const LONG_CODE_HEIGHT = 360;

    function renderPlainText(container, rawMarkdown) {
        container.replaceChildren(document.createTextNode(rawMarkdown));
    }

    function sanitizeMarkdown(rawMarkdown) {
        if (!global.marked || typeof global.marked.parse !== 'function') {
            throw new Error('marked is unavailable');
        }
        if (!global.DOMPurify || typeof global.DOMPurify.sanitize !== 'function') {
            throw new Error('DOMPurify is unavailable');
        }
        const parsed = global.marked.parse(rawMarkdown, { gfm: true, breaks: true });
        return global.DOMPurify.sanitize(parsed, {
            USE_PROFILES: { html: true },
            ADD_TAGS: ['details', 'summary'],
            FORBID_TAGS,
            FORBID_ATTR,
        });
    }

    function isAllowedHref(href) {
        if (!href) return false;
        if (
            href.startsWith('#')
            || href.startsWith('/')
            || href.startsWith('./')
            || href.startsWith('../')
        ) {
            return true;
        }
        try {
            const url = new URL(href, global.location.href);
            return ['http:', 'https:', 'mailto:'].includes(url.protocol);
        } catch (error) {
            return false;
        }
    }

    function normalizeLinks(container) {
        container.querySelectorAll('a').forEach(link => {
            const href = link.getAttribute('href');
            if (!isAllowedHref(href)) {
                link.removeAttribute('href');
                link.removeAttribute('target');
                link.removeAttribute('rel');
                return;
            }
            const url = new URL(href, global.location.href);
            if (
                ['http:', 'https:'].includes(url.protocol)
                && url.origin !== global.location.origin
            ) {
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
            }
        });
    }

    function codeLanguage(code) {
        const className = Array.from(code.classList).join(' ');
        const match = className.match(/(?:^|\s)language-([^\s]+)/);
        return match ? match[1] : 'text';
    }

    function actionButton(text, className) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = className;
        button.textContent = text;
        return button;
    }

    function enhanceCodeBlocks(container, options = {}) {
        const onCopy = typeof options.onCopy === 'function' ? options.onCopy : () => {};
        container.querySelectorAll('pre > code').forEach(code => {
            const pre = code.parentElement;
            if (pre.parentElement && pre.parentElement.classList.contains('md-code-shell')) {
                return;
            }

            try {
                if (global.hljs && typeof global.hljs.highlightElement === 'function') {
                    global.hljs.highlightElement(code);
                }
            } catch (error) {
                code.removeAttribute('data-highlighted');
            }

            const shell = document.createElement('div');
            shell.className = 'md-code-shell';
            const toolbar = document.createElement('div');
            toolbar.className = 'md-code-toolbar';
            const language = document.createElement('span');
            language.className = 'md-code-language';
            language.textContent = codeLanguage(code);
            const actions = document.createElement('span');
            actions.className = 'md-code-actions';
            const toggle = actionButton('展开代码', 'md-code-action md-code-toggle');
            toggle.hidden = true;
            const copy = actionButton('复制代码', 'md-code-action md-code-copy');

            copy.addEventListener('click', () => onCopy('复制代码', code.textContent || ''));
            toggle.addEventListener('click', () => {
                shell.classList.toggle('collapsed');
                toggle.textContent = shell.classList.contains('collapsed')
                    ? '展开代码'
                    : '收起代码';
            });

            pre.before(shell);
            shell.append(toolbar, pre);
            actions.append(toggle, copy);
            toolbar.append(language, actions);

            const lineCount = (code.textContent || '').split(/\r?\n/).length;
            if (lineCount > LONG_CODE_LINES || pre.scrollHeight > LONG_CODE_HEIGHT) {
                shell.classList.add('collapsed');
                toggle.hidden = false;
            }
        });
    }

    function renderInto(container, rawMarkdown, options = {}) {
        try {
            const safeHtml = sanitizeMarkdown(rawMarkdown);
            container.innerHTML = safeHtml;
            normalizeLinks(container);
            enhanceCodeBlocks(container, options);
            return true;
        } catch (error) {
            renderPlainText(container, rawMarkdown);
            return false;
        }
    }

    function setSourceMode(message, rawMarkdown, showSource) {
        const body = message.querySelector('.markdown-body');
        const source = message.querySelector('.assistant-source');
        const toggle = message.querySelector('.assistant-source-toggle');
        source.textContent = rawMarkdown;
        source.hidden = !showSource;
        body.hidden = showSource;
        toggle.textContent = showSource ? '返回渲染' : '查看源码';
        toggle.setAttribute('aria-pressed', String(showSource));
        return showSource;
    }

    function toggleSourceMode(message, rawMarkdown) {
        const source = message.querySelector('.assistant-source');
        return setSourceMode(message, rawMarkdown, source.hidden);
    }

    global.EasyClawMarkdown = {
        enhanceCodeBlocks,
        normalizeLinks,
        renderInto,
        setSourceMode,
        toggleSourceMode,
    };
})(window);
```

- [ ] **Step 5: Extend the default static regression test for the helper boundary**

Add these assertions immediately after `assert markdown_js.status_code == 200` in `tests/api/test_api_app.py`:

```python
    assert "DOMPurify.sanitize" in markdown_js.text
    assert "container.innerHTML = safeHtml" in markdown_js.text
    assert "function normalizeLinks" in markdown_js.text
    assert "function enhanceCodeBlocks" in markdown_js.text
    assert "function toggleSourceMode" in markdown_js.text
    assert "onclick=" not in markdown_js.text
```

- [ ] **Step 6: Run smoke and static tests and verify they pass**

Run:

```powershell
$env:EASY_CLAW_SMOKE_BROWSER = "1"
uv run pytest tests/api/test_web_markdown_smoke.py tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit the safe renderer**

Run:

```powershell
git add src/easy_claw/api/static/markdown.js tests/api/test_api_app.py tests/api/test_web_markdown_smoke.py
git commit -m "feat: add safe web markdown renderer"
```

## Task 3: Integrate Markdown with Streaming Assistant Messages

**Files:**
- Modify: `tests/api/test_api_app.py`
- Modify: `src/easy_claw/api/static/app.js`

- [ ] **Step 1: Add static integration assertions before editing the message flow**

Add these assertions after the existing `app_js` assertions in `test_web_ui_uses_split_static_assets()`:

```python
    assert "function createAssistantMessage" in app_js.text
    assert "function renderAssistantMessage" in app_js.text
    assert "function toggleAssistantSource" in app_js.text
    assert "EasyClawMarkdown.renderInto" in app_js.text
    assert "EasyClawMarkdown.toggleSourceMode" in app_js.text
    assert "message.rawMarkdown += text" in app_js.text
    assert "el.rawMarkdown || el.textContent" in app_js.text
```

- [ ] **Step 2: Run the static regression test and verify the integration is missing**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected: `FAIL` because `app.js` still appends raw token text directly.

- [ ] **Step 3: Replace assistant-token rendering with stable message-card rendering**

In `src/easy_claw/api/static/app.js`, replace the existing `appendToken()` and `finishAssistant()` functions with:

```javascript
function createAssistantMessage() {
    const message = el('div', { className: 'message assistant' });
    message.rawMarkdown = '';

    const content = el('div', { className: 'assistant-content' });
    const body = el('div', { className: 'markdown-body' });
    const source = el('pre', { className: 'assistant-source' });
    source.hidden = true;
    const cursor = el('span', { className: 'cursor' });

    const actions = el('div', { className: 'assistant-actions' });
    const copyButton = el('button', { className: 'assistant-action', text: '复制全文' });
    copyButton.type = 'button';
    copyButton.addEventListener('click', () => copyPayload('复制全文', message.rawMarkdown));
    const sourceButton = el('button', {
        className: 'assistant-action assistant-source-toggle',
        text: '查看源码',
    });
    sourceButton.type = 'button';
    sourceButton.setAttribute('aria-pressed', 'false');
    sourceButton.addEventListener('click', () => toggleAssistantSource(message));

    actions.append(copyButton, sourceButton);
    content.append(body, source, cursor);
    message.append(content, actions);
    return message;
}

function renderAssistantMessage(message) {
    const body = message.querySelector('.markdown-body');
    const source = message.querySelector('.assistant-source');
    source.textContent = message.rawMarkdown;
    if (
        window.EasyClawMarkdown
        && typeof window.EasyClawMarkdown.renderInto === 'function'
    ) {
        window.EasyClawMarkdown.renderInto(
            body,
            message.rawMarkdown,
            { onCopy: copyPayload },
        );
        return;
    }
    body.textContent = message.rawMarkdown;
}

function toggleAssistantSource(message) {
    if (
        window.EasyClawMarkdown
        && typeof window.EasyClawMarkdown.toggleSourceMode === 'function'
    ) {
        window.EasyClawMarkdown.toggleSourceMode(message, message.rawMarkdown);
        return;
    }
    const body = message.querySelector('.markdown-body');
    const source = message.querySelector('.assistant-source');
    const toggle = message.querySelector('.assistant-source-toggle');
    const showSource = source.hidden;
    source.textContent = message.rawMarkdown;
    source.hidden = !showSource;
    body.hidden = showSource;
    toggle.textContent = showSource ? '返回渲染' : '查看源码';
    toggle.setAttribute('aria-pressed', String(showSource));
}

function appendToken(text) {
    if (!currentAssistant) {
        currentAssistant = createAssistantMessage();
        msgEl.appendChild(currentAssistant);
    }
    const message = currentAssistant;
    message.rawMarkdown += text;
    renderAssistantMessage(message);
}

function finishAssistant() {
    const cursor = currentAssistant ? currentAssistant.querySelector('.cursor') : null;
    if (cursor) cursor.remove();
    currentAssistant = null;
}
```

- [ ] **Step 4: Generalize the existing clipboard helper for tool cards and assistant cards**

Replace the existing `copyToolPayload()` function in `src/easy_claw/api/static/app.js` with:

```javascript
async function copyPayload(label, content) {
    try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
            throw new Error('浏览器不支持剪贴板写入');
        }
        await navigator.clipboard.writeText(content);
        topbarStatus.textContent = label + '已复制';
    } catch (e) {
        topbarStatus.textContent = label + '失败：无法写入剪贴板';
    }
}

async function copyToolPayload(label, content) {
    return copyPayload(label, content);
}
```

- [ ] **Step 5: Preserve raw Markdown in `/save` exports**

In `downloadMarkdown()` in `src/easy_claw/api/static/app.js`, replace:

```javascript
        if (el.classList.contains('message')) {
            const role = el.classList.contains('user') ? '**用户：**' : '**easy-claw：**';
            parts.push('\n' + role + '\n\n' + el.textContent + '\n');
```

with:

```javascript
        if (el.classList.contains('message')) {
            const isUser = el.classList.contains('user');
            const role = isUser ? '**用户：**' : '**easy-claw：**';
            const content = isUser ? el.textContent : (el.rawMarkdown || el.textContent);
            parts.push('\n' + role + '\n\n' + content + '\n');
```

- [ ] **Step 6: Run focused API tests and verify the integration contract passes**

Run:

```powershell
uv run pytest tests/api/test_api_app.py -q
```

Expected: all API tests pass.

- [ ] **Step 7: Commit the streaming integration**

Run:

```powershell
git add src/easy_claw/api/static/app.js tests/api/test_api_app.py
git commit -m "feat: render streaming assistant markdown"
```

## Task 4: Style Markdown Reading, Code Blocks, and Message Actions

**Files:**
- Modify: `tests/api/test_api_app.py`
- Modify: `src/easy_claw/api/static/style.css`

- [ ] **Step 1: Add style assertions before adding selectors**

Add these assertions after the existing CSS assertions in `test_web_ui_uses_split_static_assets()`:

```python
    assert ".markdown-body" in css.text
    assert ".assistant-actions" in css.text
    assert ".assistant-source" in css.text
    assert ".md-code-toolbar" in css.text
    assert ".md-code-shell.collapsed pre" in css.text
    assert ".markdown-body table" in css.text
```

- [ ] **Step 2: Run the static regression test and verify the styles are missing**

Run:

```powershell
uv run pytest tests/api/test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected: `FAIL` because the Markdown selectors are not present.

- [ ] **Step 3: Add Markdown body and assistant-card styles**

Append this block before the existing `.tool-panel` styles in `src/easy_claw/api/static/style.css`:

```css
.message.assistant {
    white-space: normal;
}
.assistant-content {
    min-width: 0;
}
.markdown-body {
    overflow-wrap: anywhere;
}
.markdown-body > :first-child { margin-top: 0; }
.markdown-body > :last-child { margin-bottom: 0; }
.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
    color: var(--cyan-dim);
    line-height: 1.28;
    margin: 1.1em 0 0.5em;
}
.markdown-body h1 { font-size: 1.45em; }
.markdown-body h2 { font-size: 1.3em; }
.markdown-body h3 { font-size: 1.16em; }
.markdown-body p,
.markdown-body ul,
.markdown-body ol,
.markdown-body blockquote,
.markdown-body table,
.markdown-body details {
    margin: 0.65em 0;
}
.markdown-body ul,
.markdown-body ol {
    padding-left: 1.5em;
}
.markdown-body li + li {
    margin-top: 0.22em;
}
.markdown-body blockquote {
    border-left: 3px solid #00ffff55;
    color: var(--dim);
    padding: 0.2em 0 0.2em 0.9em;
}
.markdown-body a {
    color: var(--cyan-dim);
    text-decoration-color: #00ffff70;
    text-underline-offset: 2px;
}
.markdown-body :not(pre) > code {
    background: #00ffff10;
    border: 1px solid #00ffff20;
    border-radius: 4px;
    color: #b8ffff;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
    font-size: 0.9em;
    padding: 0.08em 0.3em;
}
.markdown-body table {
    border-collapse: collapse;
    display: block;
    max-width: 100%;
    overflow-x: auto;
}
.markdown-body th,
.markdown-body td {
    border: 1px solid #ffffff1c;
    padding: 6px 9px;
    text-align: left;
    white-space: nowrap;
}
.markdown-body th {
    background: #00ffff0a;
    color: var(--cyan-dim);
}
.markdown-body input[type="checkbox"] {
    accent-color: var(--pink);
    margin-right: 0.4em;
}
.markdown-body details {
    border: 1px solid #ffffff16;
    border-radius: 6px;
    padding: 6px 8px;
}
.markdown-body summary {
    color: var(--cyan-dim);
    cursor: pointer;
}
.assistant-source {
    background: rgba(0, 0, 0, 0.28);
    border: 1px solid #ffffff16;
    border-radius: 7px;
    color: var(--text);
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
    font-size: 12px;
    line-height: 1.55;
    margin: 0;
    max-height: 420px;
    overflow: auto;
    padding: 10px;
    white-space: pre-wrap;
}
.assistant-actions {
    border-top: 1px solid #ffffff10;
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin: 10px -14px -10px;
    padding: 8px 12px;
}
.assistant-action,
.md-code-action {
    background: #ffffff08;
    border: 1px solid #ffffff16;
    border-radius: 6px;
    color: var(--dim);
    cursor: pointer;
    font-family: inherit;
    font-size: 11px;
    line-height: 1.2;
    padding: 5px 8px;
}
.assistant-action:hover,
.md-code-action:hover {
    border-color: #00ffff35;
    color: var(--cyan-dim);
}
.md-code-shell {
    background: #070716;
    border: 1px solid #ffffff18;
    border-radius: 8px;
    margin: 0.75em 0;
    overflow: hidden;
}
.md-code-toolbar {
    align-items: center;
    background: #15152f;
    border-bottom: 1px solid #ffffff12;
    display: flex;
    gap: 8px;
    justify-content: space-between;
    padding: 6px 8px;
}
.md-code-language {
    color: var(--cyan-dim);
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
    font-size: 11px;
}
.md-code-actions {
    display: flex;
    gap: 6px;
}
.md-code-shell pre {
    margin: 0;
    max-width: 100%;
    overflow: auto;
}
.md-code-shell pre code {
    display: block;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
    font-size: 12px;
    line-height: 1.55;
    padding: 11px;
}
.md-code-shell.collapsed pre {
    max-height: 300px;
    overflow: hidden;
}
```

- [ ] **Step 4: Add narrow-screen adjustments**

Add these declarations inside the existing `@media (max-width: 640px)` block in `src/easy_claw/api/static/style.css`:

```css
    .message { max-width: 92%; }
    .assistant-actions {
        margin-left: -10px;
        margin-right: -10px;
    }
    .markdown-body th,
    .markdown-body td {
        padding: 5px 7px;
    }
    .md-code-toolbar {
        align-items: flex-start;
        flex-direction: column;
    }
```

- [ ] **Step 5: Run the focused static and browser tests**

Run:

```powershell
$env:EASY_CLAW_SMOKE_BROWSER = "1"
uv run pytest tests/api/test_api_app.py tests/api/test_web_markdown_smoke.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the Markdown presentation styles**

Run:

```powershell
git add src/easy_claw/api/static/style.css tests/api/test_api_app.py
git commit -m "style: improve web markdown readability"
```

## Task 5: Update User and Maintainer Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update the README Web-page description**

In `README.md`, after the paragraph ending with `用 /resume <session-id> 按前缀恢复会话。`, add:

```markdown

Web 页面会实时渲染助手回复中的 Markdown，并支持标题、列表、引用、链接、表格、任务列表和代码块。代码块支持语法高亮、复制和长内容折叠；助手回复底部可以复制原始 Markdown 或切换查看源码。工具调用卡片仍保持摘要优先的纯文本展示。
```

- [ ] **Step 2: Update the architecture document**

In `docs/architecture.md`, after the Web API paragraph containing `CLI 交互式聊天仍是默认入口。`, add:

```markdown

Web 静态前端保持无构建步骤的原生 HTML、CSS 和 JavaScript：

- `api/static/index.html` 加载页面骨架和静态依赖；
- `api/static/app.js` 管理 WebSocket、会话、斜杠命令和消息卡片；
- `api/static/markdown.js` 负责助手回复的实时 Markdown 解析、DOMPurify 清洗、链接规范化、代码块增强和源码切换；
- `api/static/style.css` 管理页面主题、工具卡片和 Markdown 排版；
- `api/static/vendor/` 固定浏览器依赖版本，使本地 Web 页面离线可用。

用户消息和工具调用详情继续按纯文本渲染。助手 Markdown 生成的 HTML 必须先经过 DOMPurify 清洗，再写入页面。
```

- [ ] **Step 3: Correct the maintainer architecture map**

In `AGENTS.md`, replace:

```markdown
- `api/static/index.html` is the current single-file web UI. It talks to `/ws/chat`, `/slash-commands`, `/sessions`, `/skills`, `/mcp`, and `/browser`.
```

with:

```markdown
- `api/static/` contains the split vanilla Web UI: `index.html`, `app.js`, `markdown.js`, `style.css`, and vendored browser assets. It talks to `/ws/chat`, `/slash-commands`, `/sessions`, `/skills`, `/mcp`, and `/browser`.
```

- [ ] **Step 4: Run a diff whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 5: Commit the documentation updates**

Run:

```powershell
git add README.md docs/architecture.md AGENTS.md
git commit -m "docs: describe web markdown rendering"
```

## Task 6: Verify the Complete Change

**Files:**
- Verify only.

- [ ] **Step 1: Run the focused API suite**

Run:

```powershell
uv run pytest tests/api/test_api_app.py -q
```

Expected: all API tests pass.

- [ ] **Step 2: Run the opt-in Markdown browser smoke suite**

Run:

```powershell
$env:EASY_CLAW_SMOKE_BROWSER = "1"
uv run pytest tests/api/test_web_markdown_smoke.py -q
```

Expected: all Markdown browser smoke tests pass.

- [ ] **Step 3: Run the full Python test suite**

Run:

```powershell
$env:EASY_CLAW_SMOKE_BROWSER = $null
uv run pytest
```

Expected: all default tests pass; opt-in real-browser smoke tests are skipped.

- [ ] **Step 4: Run Ruff**

Run:

```powershell
uv run ruff check .
```

Expected: no lint errors.

- [ ] **Step 5: Check for accidental generated or runtime files**

Run:

```powershell
git status --short
```

Expected: only intentional source, test, documentation, and vendored static files are modified or added.

- [ ] **Step 6: Start the local Web server for visual verification**

Run:

```powershell
uv run easy-claw serve
```

Expected: the server starts and the Web chat page is available at `http://127.0.0.1:8787/`.

- [ ] **Step 7: Verify the local page in the in-app Browser**

Open `http://127.0.0.1:8787/` with the in-app Browser and send a prompt that requests:

```text
请用 Markdown 回复：包含二级标题、列表、引用、表格、任务列表、一个带 onclick 的 HTML 链接、一个 javascript: 链接，以及超过 20 行的 Python 代码块。
```

Confirm:

- headings, lists, quotes, tables, and task lists render while tokens stream;
- the safe HTML link renders without executable attributes;
- the `javascript:` link is inert;
- the code block shows `python`, syntax colors, `复制代码`, and collapsed long-code controls;
- the reply bottom bar shows `复制全文` and `查看源码`;
- source view preserves the original Markdown and can return to rendered view;
- the page remains usable at a narrow viewport.

- [ ] **Step 8: Stop the local server and record final status**

Stop `uv run easy-claw serve` with `Ctrl+C`, then run:

```powershell
git status -sb
```

Expected: the branch contains only the planned commits and no runtime-state files.

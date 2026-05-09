# Frontend Beautify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 easy-claw 的 Web 聊天页面从单栏暗色布局重写为赛博霓虹双栏布局（左侧会话列表 + 右侧聊天区），后端零改动。

**Architecture:** 单文件 `index.html`，全部 inline CSS + vanilla JS。CSS 变量驱动配色，grid 布局实现双栏。JS 在现有 WebSocket/斜杠命令逻辑基础上增加侧栏会话管理。

**Tech Stack:** HTML5 + CSS3 (custom properties, grid, backdrop-filter, animations) + Vanilla JS (WebSocket, fetch, DOM)

---

### Task 1: 重写 CSS 变量和基础样式

**Files:**
- Modify: `src/easy_claw/api/static/index.html` (替换 `<style>` 块前半部分)

- [ ] **Step 1: 替换 CSS 变量和 reset/base/layout**

将现有 `:root` 到 `body` 的样式替换为：

```css
:root {
    --bg-deep: #0a0a1a;
    --bg-surface: #0d0d25;
    --bg-card: #12122a;
    --border: #1a1a3a;
    --border-glow: #ff69b430;
    --text: #e6edf3;
    --dim: #8b949e;
    --pink: #ff69b4;
    --pink-deep: #ff1493;
    --cyan: #00ffff;
    --cyan-dim: #66ffff;
    --green: #3fb950;
    --red: #f85149;
    --sidebar-width: 220px;
    --glow-pink: 0 0 12px #ff69b440;
    --glow-cyan: 0 0 8px #00ffff20;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
    background: var(--bg-deep);
    color: var(--text);
    height: 100vh;
    display: flex;
    overflow: hidden;
}
#app {
    display: flex;
    width: 100%;
    height: 100%;
}
```

- [ ] **Step 2: 添加 CSS 动画定义**

```css
@keyframes blink { 50% { opacity: 0; } }
@keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 8px #ff69b430; }
    50% { box-shadow: 0 0 18px #ff69b460; }
}
@keyframes cyan-pulse {
    0%, 100% { box-shadow: 0 0 4px #00ffff30; }
    50% { box-shadow: 0 0 12px #00ffff50; }
}
@keyframes border-glow {
    0%, 100% { border-color: #ff69b430; box-shadow: 0 0 6px #ff69b410; }
    50% { border-color: #ff69b460; box-shadow: 0 0 14px #ff69b425; }
}
```

- [ ] **Step 3: 提交**

```bash
git add src/easy_claw/api/static/index.html
git commit -m "feat: 替换 CSS 变量为基础赛博霓虹配色，添加动画关键帧"
```

---

### Task 2: 重写 CSS 组件样式

**Files:**
- Modify: `src/easy_claw/api/static/index.html` (继续替换 `<style>` 块)

- [ ] **Step 1: 侧栏样式**

```css
#sidebar {
    width: var(--sidebar-width);
    background: linear-gradient(180deg, #0d0d25 0%, #0a0a1a 100%);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
}
#sidebar .sb-header {
    padding: 14px 12px;
    border-bottom: 1px solid var(--border);
}
#sidebar .sb-logo {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
#sidebar .sb-logo .icon {
    color: var(--pink);
    font-weight: 700;
    font-size: 14px;
}
#sidebar .sb-logo .ver {
    font-size: 10px;
    color: var(--cyan-dim);
    background: #00ffff12;
    padding: 1px 6px;
    border-radius: 8px;
}
#new-chat-btn {
    width: 100%;
    background: linear-gradient(135deg, var(--pink), var(--pink-deep));
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 9px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: var(--glow-pink);
    transition: all 0.2s;
}
#new-chat-btn:hover {
    box-shadow: 0 0 20px #ff69b460;
    transform: translateY(-1px);
}
#new-chat-btn:active { transform: translateY(0); }
#session-list {
    flex: 1;
    overflow-y: auto;
    padding: 6px;
}
#session-list .session-item {
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 6px;
    margin-bottom: 2px;
    cursor: pointer;
    transition: all 0.15s;
}
#session-list .session-item:hover {
    background: #00ffff06;
    border-color: #00ffff15;
}
#session-list .session-item.active {
    background: #00ffff08;
    border-color: #00ffff30;
    box-shadow: var(--glow-cyan);
}
#session-list .session-item .sess-title {
    font-size: 12px;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
#session-list .session-item .sess-meta {
    font-size: 10px;
    color: var(--dim);
    margin-top: 2px;
    display: flex;
    justify-content: space-between;
}
#session-list .session-item.active .sess-meta { color: var(--cyan-dim); }
#sb-status {
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    font-size: 10px;
}
#sb-status .status-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 3px;
    color: var(--dim);
}
#sb-status .status-row .val { color: var(--text); }
#sb-status .status-row .val.cyan { color: var(--cyan-dim); }
#sb-status .status-row .val.pink { color: var(--pink); }
```

- [ ] **Step 2: 主区域和顶栏样式**

```css
#main-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
}
#topbar {
    padding: 8px 16px;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
}
#conn-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
    flex-shrink: 0;
    transition: all 0.3s;
}
#conn-dot.disconnected {
    background: var(--red);
    box-shadow: 0 0 6px var(--red);
}
#topbar-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
}
#topbar-status {
    font-size: 11px;
    color: var(--dim);
    margin-left: auto;
}
```

- [ ] **Step 3: 消息区样式**

```css
#messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.message {
    max-width: 80%;
    padding: 10px 14px;
    border-radius: 10px;
    line-height: 1.55;
    word-break: break-word;
    white-space: pre-wrap;
    animation: msg-in 0.2s ease-out;
}
@keyframes msg-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
.message.user {
    align-self: flex-end;
    background: linear-gradient(135deg, var(--pink), var(--pink-deep));
    color: #fff;
    border-bottom-right-radius: 3px;
    box-shadow: 0 0 12px #ff69b420;
}
.message.assistant {
    align-self: flex-start;
    background: rgba(18, 18, 42, 0.75);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    border-bottom-left-radius: 3px;
    min-width: 60px;
}
.message.assistant .cursor {
    display: inline-block;
    width: 7px;
    height: 15px;
    background: var(--pink);
    box-shadow: 0 0 6px var(--pink);
    animation: blink 1s step-end infinite;
    vertical-align: text-bottom;
    margin-left: 2px;
}
```

- [ ] **Step 4: 工具面板样式**

```css
.tool-panel {
    align-self: stretch;
    border: 1px solid #00ffff30;
    border-radius: 8px;
    overflow: hidden;
    margin: 4px 0;
    box-shadow: 0 0 8px #00ffff10;
    animation: msg-in 0.2s ease-out;
}
.tool-panel.result { border-color: #3fb95030; box-shadow: 0 0 8px #3fb95010; }
.tool-panel .header {
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    user-select: none;
}
.tool-panel .header.call { background: #00ffff08; color: var(--cyan-dim); }
.tool-panel .header.result { background: #3fb95008; color: var(--green); }
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
.tool-panel .arrow { transition: transform 0.2s; }
.tool-panel.open .arrow { transform: rotate(90deg); }
```

- [ ] **Step 5: 输入区和 Modal 样式**

```css
#input-area {
    background: var(--bg-surface);
    border-top: 1px solid var(--border);
    padding: 12px 16px;
    display: flex;
    gap: 10px;
    align-items: flex-end;
    flex-shrink: 0;
}
#input-area textarea {
    flex: 1;
    background: var(--bg-deep);
    color: var(--text);
    border: 1px solid var(--border-glow);
    border-radius: 10px;
    padding: 10px 14px;
    font-family: inherit;
    font-size: 14px;
    resize: none;
    min-height: 42px;
    max-height: 160px;
    line-height: 1.4;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
}
#input-area textarea:focus {
    border-color: var(--pink);
    box-shadow: 0 0 10px #ff69b425;
}
#input-area textarea:disabled {
    border-color: var(--border);
    box-shadow: none;
}
#send-btn {
    background: linear-gradient(135deg, var(--pink), var(--pink-deep));
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: var(--glow-pink);
    transition: all 0.2s;
    flex-shrink: 0;
}
#send-btn:hover { box-shadow: 0 0 18px #ff69b460; transform: translateY(-1px); }
#send-btn:active { transform: translateY(0); }
#send-btn:disabled {
    background: var(--border);
    box-shadow: none;
    cursor: not-allowed;
    transform: none;
}
.modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(2px);
    z-index: 100;
    align-items: center;
    justify-content: center;
}
.modal-overlay.show { display: flex; }
.modal {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    max-width: 500px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 0 30px #00000060;
}
.modal h2 { color: var(--cyan-dim); margin-bottom: 12px; font-size: 18px; }
.modal table { width: 100%; border-collapse: collapse; font-size: 13px; }
.modal td { padding: 6px 0; }
.modal td:first-child {
    color: var(--cyan-dim);
    font-weight: 600;
    font-family: monospace;
    width: 110px;
}
.modal .close {
    margin-top: 16px;
    background: linear-gradient(135deg, var(--pink), var(--pink-deep));
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: var(--glow-pink);
    transition: all 0.2s;
}
.modal .close:hover { box-shadow: 0 0 16px #ff69b460; }
```

- [ ] **Step 6: 提交**

```bash
git add src/easy_claw/api/static/index.html
git commit -m "feat: 完成全部 CSS 组件样式 — 侧栏/顶栏/消息/工具面板/输入/弹窗"
```

---

### Task 3: 重写 HTML 结构

**Files:**
- Modify: `src/easy_claw/api/static/index.html` (替换 `<body>` 内 HTML)

- [ ] **Step 1: 替换 HTML 为双栏结构**

删除旧 HTML（`#banner`、`#status-line`），替换为：

```html
<div id="app">
    <nav id="sidebar">
        <div class="sb-header">
            <div class="sb-logo">
                <span class="icon">&#9670; easy-claw</span>
                <span class="ver">v0.5</span>
            </div>
            <button id="new-chat-btn">+ 新对话</button>
        </div>
        <div id="session-list"></div>
        <div id="sb-status">
            <div class="status-row"><span>模型</span><span class="val cyan" id="sb-model">-</span></div>
            <div class="status-row"><span>工作区</span><span class="val" id="sb-workspace">-</span></div>
            <div class="status-row"><span>Token</span><span class="val pink" id="sb-tokens">0</span></div>
        </div>
    </nav>
    <div id="main-area">
        <div id="topbar">
            <span id="conn-dot" class="disconnected"></span>
            <span id="topbar-title">easy-claw</span>
            <span id="topbar-status">连接中...</span>
        </div>
        <div id="messages"></div>
        <div id="input-area">
            <textarea id="input" rows="1" placeholder="输入消息... (Enter 发送, Shift+Enter 换行)" disabled></textarea>
            <button id="send-btn" disabled>发送</button>
        </div>
    </div>
</div>
<div class="modal-overlay" id="modal-overlay">
    <div class="modal" id="modal-content"></div>
</div>
```

- [ ] **Step 2: 提交**

```bash
git add src/easy_claw/api/static/index.html
git commit -m "feat: 重写 HTML 为双栏布局结构（侧栏 + 主聊天区）"
```

---

### Task 4: 重写 JS — DOM 引用和核心通信

**Files:**
- Modify: `src/easy_claw/api/static/index.html` (重写 `<script>` 块前半部分)

- [ ] **Step 1: 更新 DOM 引用和状态变量**

```javascript
const msgEl = document.getElementById('messages');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const dotEl = document.getElementById('conn-dot');
const topbarTitle = document.getElementById('topbar-title');
const topbarStatus = document.getElementById('topbar-status');
const modalOverlay = document.getElementById('modal-overlay');
const modalContent = document.getElementById('modal-content');
const sessionListEl = document.getElementById('session-list');
const newChatBtn = document.getElementById('new-chat-btn');
const sbModel = document.getElementById('sb-model');
const sbWorkspace = document.getElementById('sb-workspace');
const sbTokens = document.getElementById('sb-tokens');

let ws = null;
let currentAssistant = null;
let modelName = '';
let workspace = '';
let version = '';
let sessionId = '';
let turnCount = 0;
let totalTokens = {};
let slashCommands = null;
let sessions = [];
```

- [ ] **Step 2: 保留并适配 WebSocket 连接函数**

`buildWsUrl()`、`connect()`、`disconnect()` 函数逻辑不变，仅修改 `connect()` 中状态更新目标：

```javascript
function buildWsUrl(resumeSessionId) {
    let url = 'ws://' + location.host + '/ws/chat';
    if (resumeSessionId) {
        url += '?session_id=' + encodeURIComponent(resumeSessionId);
    }
    return url;
}

// connect() 函数: 同现有逻辑，仅将连接状态更新改为操作 topbar 元素
// 具体修改在 Task 6 中整合
```

- [ ] **Step 3: 保留并适配消息处理函数**

`handleMessage()`、`appendToken()`、`finishAssistant()`、`addToolPanel()`、`togglePanel()`、`formatContent()`、`escapeHtml()`、`scrollBottom()` 函数保持不变。

- [ ] **Step 4: 保留 send() 函数**

`send()` 函数逻辑不变。

- [ ] **Step 5: 提交**

```bash
git add src/easy_claw/api/static/index.html
git commit -m "feat: 更新 JS DOM 引用，适配新结构；保留核心 WS 和消息逻辑"
```

---

### Task 5: 重写 JS — 侧栏会话管理

**Files:**
- Modify: `src/easy_claw/api/static/index.html` (在 `<script>` 中添加侧栏函数)

- [ ] **Step 1: 添加会话列表加载和渲染**

```javascript
async function loadSessions() {
    try {
        sessions = await fetchJson('/sessions');
    } catch (e) {
        sessions = [];
    }
    renderSessionList();
}

function renderSessionList() {
    if (sessions.length === 0) {
        sessionListEl.innerHTML = '<div style="padding:12px;font-size:11px;color:var(--dim);text-align:center;">暂无会话</div>';
        return;
    }
    sessionListEl.innerHTML = sessions.map(s => {
        const active = s.id === sessionId ? ' active' : '';
        const shortId = s.id.slice(0, 8);
        const time = relativeTime(s.updated_at);
        return '<div class="session-item' + active + '" data-sid="' + s.id + '" onclick="switchSession(\'' + s.id + '\')">' +
            '<div class="sess-title">' + escapeHtml(s.title || '未命名') + '</div>' +
            '<div class="sess-meta"><span>' + escapeHtml(s.model || '-') + '</span><span>' + time + '</span></div>' +
            '</div>';
    }).join('');
}

function relativeTime(iso) {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return mins + '分钟前';
    const hours = Math.floor(mins / 60);
    if (hours < 24) return hours + '小时前';
    return Math.floor(hours / 24) + '天前';
}
```

- [ ] **Step 2: 添加 postJson 辅助、会话切换和新对话**

```javascript
async function postJson(path, body) {
    const resp = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!resp.ok) {
        let detail = resp.statusText;
        try { const p = await resp.json(); detail = p.detail || detail; } catch (e) {}
        throw new Error(detail);
    }
    return resp.json();
}

async function switchSession(targetId) {
    if (targetId === sessionId) return;
    const oldSocket = ws;
    msgEl.innerHTML = '';
    currentAssistant = null;
    turnCount = 0;
    totalTokens = {};
    sessionId = targetId;
    renderSessionList();
    updateStatusBar();
    topbarStatus.textContent = '切换会话中...';
    connect(targetId);
    if (oldSocket && oldSocket.readyState !== WebSocket.CLOSED) oldSocket.close();
}

async function newChat() {
    try {
        const created = await postJson('/sessions', { title: '新会话' });
        topbarStatus.textContent = '已创建新会话';
        await loadSessions();
        switchSession(created.id);
    } catch (e) {
        topbarStatus.textContent = '创建失败：' + e.message;
    }
}
```

- [ ] **Step 3: 添加状态栏更新**

```javascript
function updateStatusBar() {
    sbModel.textContent = modelName || '-';
    sbWorkspace.textContent = workspace || '-';
    sbTokens.textContent = (totalTokens.total || 0).toLocaleString();
}

function updateTopbar() {
    topbarTitle.textContent = sessionId ? (sessionId.slice(0, 8)) : 'easy-claw';
}
```

- [ ] **Step 4: 绑定侧栏事件**

```javascript
newChatBtn.addEventListener('click', newChat);
```

- [ ] **Step 5: 提交**

```bash
git add src/easy_claw/api/static/index.html
git commit -m "feat: 添加侧栏会话管理 — 列表渲染/切换/新建/状态栏"
```

---

### Task 6: 重写 JS — 整合所有处理函数

**Files:**
- Modify: `src/easy_claw/api/static/index.html` (整合 `<script>` 中所有函数)

- [ ] **Step 1: 整合 connect() 函数**

```javascript
function connect(resumeSessionId) {
    const socket = new WebSocket(buildWsUrl(resumeSessionId));
    ws = socket;
    socket.onopen = () => {
        dotEl.classList.remove('disconnected');
        inputEl.disabled = false;
        sendBtn.disabled = false;
        topbarStatus.textContent = '就绪';
    };
    socket.onclose = () => {
        if (socket !== ws) return;
        dotEl.classList.add('disconnected');
        inputEl.disabled = true;
        sendBtn.disabled = true;
        topbarStatus.textContent = '连接已断开，2 秒后重连...';
        setTimeout(() => connect(resumeSessionId), 2000);
    };
    socket.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        handleMessage(msg);
    };
}
```

- [ ] **Step 2: 整合 handleMessage() 函数 — 更新状态位置**

```javascript
function handleMessage(msg) {
    switch (msg.type) {
        case 'banner':
            modelName = msg.model || '';
            workspace = msg.workspace || '';
            version = msg.version || '';
            sessionId = msg.session_id || '';
            updateTopbar();
            updateStatusBar();
            topbarStatus.textContent = '就绪';
            loadSessions();
            break;
        case 'token':
            appendToken(msg.content);
            break;
        case 'tool_call_start':
            finishAssistant();
            addToolPanel('call', msg.tool_name, msg.tool_args);
            topbarStatus.textContent = '调用工具：' + (msg.tool_name || '未知');
            break;
        case 'tool_call_result':
            addToolPanel('result', msg.tool_name, msg.tool_result || msg.content);
            topbarStatus.textContent = '就绪';
            break;
        case 'approval_required':
            finishAssistant();
            topbarStatus.textContent = '工具执行需要确认（已自动批准）';
            break;
        case 'done':
            finishAssistant();
            if (msg.usage) {
                totalTokens = msg.usage;
                updateStatusBar();
            }
            turnCount++;
            topbarStatus.textContent = '就绪';
            break;
        case 'error':
            finishAssistant();
            topbarStatus.textContent = '错误：' + msg.content;
            break;
    }
    scrollBottom();
}
```

- [ ] **Step 3: 保留 send() 函数 — 适配新状态栏**

```javascript
function send() {
    const text = inputEl.value;
    if (!text.trim() || !ws || ws.readyState !== WebSocket.OPEN) return;
    const trimmed = text.trim();
    const lowered = trimmed.toLowerCase();

    if (trimmed.startsWith('/') || ['exit', 'quit', ':q'].includes(lowered)) {
        handleSlash(trimmed);
        inputEl.value = '';
        return;
    }

    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.textContent = text;
    msgEl.appendChild(userMsg);

    ws.send(text);
    inputEl.value = '';
    inputEl.style.height = '';
    topbarStatus.textContent = '思考中...';
}
```

- [ ] **Step 4: 保留 fetch 辅助函数和斜杠命令函数**

`loadSlashCommands()`、`fetchJson()`、`handleSlash()`、`showCommandHelp()`、`showSkills()`、`showMcp()`、`showBrowser()`、`showSessions()`、`resumeSession()`、`showModal()`、`closeModal()`、`yesNo()` 函数保持不变。

`resumeSession()` 需要在切换后刷新侧栏：

```javascript
async function resumeSession(sessionPrefix) {
    if (!sessionPrefix) {
        topbarStatus.textContent = '用法：/resume <session-id>';
        return;
    }
    const session = await fetchJson('/sessions/resolve/' + encodeURIComponent(sessionPrefix));
    switchSession(session.id);
}
```

- [ ] **Step 5: 保留 Markdown 导出、键盘事件和初始化**

`downloadMarkdown()`、`inputEl` 键盘事件、`sendBtn` click 事件、Escape 关闭弹窗逻辑不变。

初始化代码：

```javascript
inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
    }
});

inputEl.addEventListener('input', () => {
    inputEl.style.height = '';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
});

sendBtn.addEventListener('click', send);

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) closeModal();
});

connect();
loadSessions();
```

- [ ] **Step 6: 提交**

```bash
git add src/easy_claw/api/static/index.html
git commit -m "feat: 整合所有 JS 逻辑 — WS/消息/侧栏/斜杠命令/导出/键盘"
```

---

### Task 7: 手动验证

- [ ] **Step 1: 启动 API 服务**

```bash
uv run easy-claw serve
```

- [ ] **Step 2: 验证页面加载**

打开 `http://127.0.0.1:8787/`，检查：
- [ ] 双栏布局正确渲染（左侧 220px 侧栏，右侧聊天区占满）
- [ ] 侧栏显示 Logo、版本号、「新对话」按钮
- [ ] 顶栏显示连接状态点（红色断开状态 → 绿色已连接状态）
- [ ] 配色为深蓝黑底 + 粉色/青色强调

- [ ] **Step 3: 验证 WebSocket 连接**

- [ ] 页面加载后自动连接，连接点变绿发光
- [ ] 输入框和发送按钮变为可用
- [ ] 顶栏显示「就绪」

- [ ] **Step 4: 验证消息收发**

- [ ] 输入文字发送，用户气泡显示在右侧（粉渐变）
- [ ] 助手回复流式渲染，打字光标闪烁
- [ ] 助手气泡为玻璃态（半透明 + 边框光晕）

- [ ] **Step 5: 验证工具面板**

- [ ] 发送需要工具调用的消息（如 "搜索一下 Python"）
- [ ] 工具调用面板显示青色边框
- [ ] 工具结果面板显示绿色边框
- [ ] 面板可折叠/展开

- [ ] **Step 6: 验证会话列表**

- [ ] 刷新页面，侧栏显示历史会话列表
- [ ] 当前激活会话有青边框高亮
- [ ] 显示会话标题、模型、相对时间

- [ ] **Step 7: 验证新对话**

- [ ] 点击「+ 新对话」，创建新会话
- [ ] 消息区清空，侧栏新增会话项

- [ ] **Step 8: 验证会话切换**

- [ ] 点击侧栏其他会话，切换到该会话
- [ ] 消息区清空，连接重新建立

- [ ] **Step 9: 验证侧栏状态**

- [ ] 底部状态栏显示当前模型、工作区、Token 用量
- [ ] Token 用量在收到 done 事件后更新

- [ ] **Step 10: 验证斜杠命令**

- [ ] 输入 `/help` 弹出命令列表弹窗
- [ ] 输入 `/status` 显示会话状态
- [ ] 输入 `/skills` 显示 skill 来源
- [ ] 输入 `/mcp` 显示 MCP 状态
- [ ] 输入 `/sessions` 显示历史会话（弹窗）
- [ ] 输入 `/resume <id>` 切换会话
- [ ] 输入 `/clear` 清空消息区

- [ ] **Step 11: 验证断线重连**

- [ ] 停止 API 服务，观察连接点变红
- [ ] 状态显示「连接已断开，2 秒后重连...」
- [ ] 重启服务，自动恢复连接

- [ ] **Step 12: 验证 Markdown 导出**

- [ ] 输入 `/save`，下载 .md 文件
- [ ] 文件内容包含会话信息和对话记录

- [ ] **Step 13: 提交最终版本**

```bash
git add src/easy_claw/api/static/index.html
git commit -m "chore: 手动验证通过，前端美化完成"
```

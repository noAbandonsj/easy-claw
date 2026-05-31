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
        keys: ['mcp__', 'mcp'],
        category: 'MCP',
        explanation: '调用 MCP 服务暴露的外部工具。',
    },
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
];

function el(tag, options = {}, children = []) {
    const node = document.createElement(tag);
    if (options.className) node.className = options.className;
    if (options.text !== undefined) node.textContent = String(options.text);
    if (options.style) Object.assign(node.style, options.style);
    for (const child of children) {
        node.append(child);
    }
    return node;
}

function heading(text) {
    return el('h2', { text });
}

function infoText(text) {
    return el(
        'p',
        {
            text,
            style: { marginTop: '12px', fontSize: '13px', color: 'var(--dim)' },
        },
    );
}

function tableFromRows(rows) {
    const table = el('table');
    rows.forEach(([label, value]) => {
        const row = el('tr');
        row.append(el('td', { text: label }), el('td', { text: value }));
        table.append(row);
    });
    return table;
}

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

function clearMessages() {
    msgEl.replaceChildren();
    currentAssistant = null;
}

function buildWsUrl(resumeSessionId) {
    let url = 'ws://' + location.host + '/ws/chat';
    if (resumeSessionId) {
        url += '?session_id=' + encodeURIComponent(resumeSessionId);
    }
    return url;
}

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

function disconnect() {
    const socket = ws;
    ws = null;
    dotEl.classList.add('disconnected');
    inputEl.disabled = true;
    sendBtn.disabled = true;
    if (socket && socket.readyState !== WebSocket.CLOSED) socket.close();
}

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

function appendToken(text) {
    if (!currentAssistant) {
        currentAssistant = document.createElement('div');
        currentAssistant.className = 'message assistant';
        currentAssistant.append(el('span', { className: 'cursor' }));
        msgEl.appendChild(currentAssistant);
    }
    const cursor = currentAssistant.querySelector('.cursor');
    cursor.before(document.createTextNode(text));
}

function finishAssistant() {
    const cursor = currentAssistant ? currentAssistant.querySelector('.cursor') : null;
    if (cursor) cursor.remove();
    currentAssistant = null;
}

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
        topbarStatus.textContent = label + '失败：无法写入剪贴板';
    }
}

function formatContent(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    try { return JSON.stringify(val, null, 2); } catch (e) { return String(val); }
}

function scrollBottom() {
    msgEl.scrollTop = msgEl.scrollHeight;
}

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

async function loadSlashCommands() {
    if (slashCommands) return slashCommands;
    const response = await fetch('/slash-commands');
    if (!response.ok) throw new Error('无法加载命令列表');
    slashCommands = await response.json();
    return slashCommands;
}

async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) {
        let detail = response.statusText;
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        } catch (e) {}
        throw new Error(detail);
    }
    return response.json();
}

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

async function loadSessions() {
    try {
        sessions = await fetchJson('/sessions');
    } catch (e) {
        sessions = [];
    }
    renderSessionList();
}

function renderSessionList() {
    sessionListEl.replaceChildren();
    if (sessions.length === 0) {
        sessionListEl.append(el('div', { className: 'empty-state', text: '暂无会话' }));
        return;
    }
    sessions.forEach(s => {
        const active = s.id === sessionId ? ' active' : '';
        const time = relativeTime(s.updated_at);
        const item = el('div', { className: 'session-item' + active });
        item.dataset.sid = s.id;
        item.addEventListener('click', () => switchSession(s.id));
        const meta = el('div', { className: 'sess-meta' });
        meta.append(el('span', { text: s.model || '-' }), el('span', { text: time }));
        item.append(el('div', { className: 'sess-title', text: s.title || '未命名' }), meta);
        sessionListEl.append(item);
    });
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

async function switchSession(targetId) {
    if (targetId === sessionId) return;
    const oldSocket = ws;
    clearMessages();
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

function updateStatusBar() {
    sbModel.textContent = modelName || '-';
    sbWorkspace.textContent = workspace || '-';
    sbTokens.textContent = (totalTokens.total || 0).toLocaleString();
}

function updateTopbar() {
    topbarTitle.textContent = sessionId ? sessionId.slice(0, 8) : 'easy-claw';
}

async function handleSlash(cmd) {
    const parts = cmd.trim().split(/\s+/);
    const token = parts[0].toLowerCase();
    const args = parts.slice(1).join(' ');
    try {
        switch (token) {
        case '/help':
            await showCommandHelp(args);
            break;
        case '/clear':
            clearMessages();
            topbarStatus.textContent = '已清空对话视图（服务端会话仍保留）';
            break;
        case '/status':
            showModal(
                heading('会话状态'),
                tableFromRows([
                    ['模型', modelName],
                    ['工作区', workspace],
                    ['版本', version],
                    ['会话', sessionId],
                    ['轮次', String(turnCount)],
                    ['Token', (totalTokens.total || 0).toLocaleString()],
                ]),
            );
            break;
        case '/save':
            downloadMarkdown();
            break;
        case '/skills':
            await showSkills();
            break;
        case '/mcp':
            await showMcp();
            break;
        case '/browser':
            await showBrowser();
            break;
        case '/sessions':
            await showSessions();
            break;
        case '/resume':
            await resumeSession(args);
            break;
        case '/exit':
        case '/quit':
        case 'exit':
        case 'quit':
        case ':q':
            topbarStatus.textContent = '已断开连接';
            disconnect();
            break;
        default:
            if (['/workspace', '/model', '/doctor', '/delete-session'].includes(token)) {
                topbarStatus.textContent = token + ' 目前仅支持 CLI。请使用 uv run easy-claw。';
            } else {
                topbarStatus.textContent = '未知命令：' + cmd;
            }
        }
    } catch (e) {
        topbarStatus.textContent = '命令执行失败：' + e.message;
    }
}

async function showCommandHelp(commandName) {
    const commands = await loadSlashCommands();
    if (commandName) {
        let normalized = commandName.trim().toLowerCase();
        if (normalized && !normalized.startsWith('/') && !['exit', 'quit', ':q'].includes(normalized)) {
            normalized = '/' + normalized;
        }
        const command = commands.find(c => c.name === normalized || (c.aliases || []).includes(normalized));
        if (!command) {
            topbarStatus.textContent = '未知命令：' + commandName;
            return;
        }
        showModal(
            heading(command.usage),
            tableFromRows([
                ['类别', command.group],
                ['说明', command.description],
                ['别名', (command.aliases || []).join(', ') || '-'],
            ]),
        );
        return;
    }
    showModal(
        heading('聊天内斜杠命令'),
        tableFromRows(commands.map(c => [c.usage, c.description])),
        infoText('命令定义来自 CLI slash registry；部分配置类命令在网页端仅显示提示。'),
    );
}

async function showSkills() {
    const payload = await fetchJson('/skills');
    const rows = payload.sources.map(source => [
        source.label,
        source.skill_count + ' 个 | ' + source.backend_path + ' | ' + source.filesystem_path,
    ]);
    showModal(
        heading('Skill 来源'),
        tableFromRows(rows.length ? rows : [['无', '没有找到 skill 来源']]),
        infoText('共 ' + payload.source_count + ' 个来源，' + payload.skill_count + ' 个 skill。'),
    );
}

async function showMcp() {
    const payload = await fetchJson('/mcp');
    showModal(
        heading('MCP'),
        tableFromRows([
            ['模式', payload.mode],
            ['状态', payload.status],
            ['配置', payload.config_path],
            ['服务数', payload.server_count],
        ]),
    );
}

async function showBrowser() {
    const payload = await fetchJson('/browser');
    showModal(
        heading('浏览器工具'),
        tableFromRows([
            ['启用', yesNo(payload.enabled)],
            ['无头模式', yesNo(payload.headless)],
            ['Chromium', yesNo(payload.chromium_installed)],
            ['Headless', yesNo(payload.chromium_headless_installed)],
        ]),
    );
}

async function showSessions() {
    const sessions = await fetchJson('/sessions');
    const rows = sessions.map(session => [
        session.id.slice(0, 8),
        session.title + ' | ' + (session.model || '-') + ' | ' + session.updated_at.slice(0, 19),
    ]);
    showModal(
        heading('历史会话'),
        tableFromRows(rows.length ? rows : [['无', '没有找到会话']]),
        infoText('使用 /resume <session-id> 可按前缀恢复。'),
    );
}

async function resumeSession(sessionPrefix) {
    if (!sessionPrefix) {
        topbarStatus.textContent = '用法：/resume <session-id>';
        return;
    }
    const session = await fetchJson('/sessions/resolve/' + encodeURIComponent(sessionPrefix));
    switchSession(session.id);
}

function yesNo(value) {
    return value ? '是' : '否';
}

function showModal(...nodes) {
    const closeButton = el('button', { className: 'close', text: '关闭' });
    closeButton.addEventListener('click', closeModal);
    modalContent.replaceChildren(...nodes, closeButton);
    modalOverlay.classList.add('show');
}

function closeModal() {
    modalOverlay.classList.remove('show');
}

modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) closeModal();
});

function downloadMarkdown() {
    const parts = ['# easy-claw 对话记录\n',
        '\n- **会话：** `' + sessionId + '`',
        '- **模型：** ' + modelName,
        '- **工作区：** ' + workspace,
        '- **导出时间：** ' + new Date().toISOString().replace('T',' ').slice(0,19),
        '\n---\n'];
    const children = msgEl.children;
    for (let i = 0; i < children.length; i++) {
        const el = children[i];
        if (el.classList.contains('message')) {
            const role = el.classList.contains('user') ? '**用户：**' : '**easy-claw：**';
            parts.push('\n' + role + '\n\n' + el.textContent + '\n');
        } else if (el.classList.contains('tool-panel')) {
            const header = el.querySelector('.header')?.textContent || '工具';
            const body = el.querySelector('.body')?.textContent || '';
            parts.push('\n> ' + header + '\n> \n> ' + body.replace(/\n/g, '\n> ') + '\n');
        }
    }
    const blob = new Blob([parts.join('\n')], {type: 'text/markdown'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'easy-claw-' + sessionId + '.md';
    a.click();
    topbarStatus.textContent = '对话记录已下载';
}

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

newChatBtn.addEventListener('click', newChat);

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

connect();
loadSessions();

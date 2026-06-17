import { fetchJson, postJson } from './api.js';
import { el, elements, scrollBottom } from './dom.js';
import { downloadMarkdown as exportMarkdown } from './exportMarkdown.js';
import { closeModal, showModal } from './modal.js';
import {
    appendAssistantToken,
    appendUserMessage,
    clearMessages as clearMessageView,
    finishAssistant,
} from './render/messages.js';
import { createToolPanel } from './render/toolPanel.js';
import { handleSlash } from './slash.js';
import { connectChat, disconnectChat } from './socket.js';
import { resetConversationState, state } from './state.js';
import { statusForStreamEvent } from './status.js';
import { ToolRunStore } from './tools.js';

const toolRunStore = new ToolRunStore();
const toolPanels = new Map();

function setStatus(text) {
    elements.topbarStatus.textContent = text;
}

function clearMessages() {
    clearMessageView(state, elements.msgEl, toolRunStore, toolPanels);
}

function connect(resumeSessionId) {
    const socket = connectChat({
        resumeSessionId,
        onOpen: () => {
            elements.dotEl.classList.remove('disconnected');
            elements.inputEl.disabled = false;
            elements.sendBtn.disabled = false;
            setStatus('就绪');
        },
        onClose: () => {
            if (socket !== state.ws) return;
            elements.dotEl.classList.add('disconnected');
            elements.inputEl.disabled = true;
            elements.sendBtn.disabled = true;
            setStatus('连接已断开，2 秒后重连...');
            setTimeout(() => connect(resumeSessionId), 2000);
        },
        onMessage: handleMessage,
    });
    state.ws = socket;
}

function disconnect() {
    const socket = state.ws;
    state.ws = null;
    elements.dotEl.classList.add('disconnected');
    elements.inputEl.disabled = true;
    elements.sendBtn.disabled = true;
    disconnectChat(socket);
}

function handleMessage(msg) {
    const nextStatus = statusForStreamEvent(msg);
    switch (msg.type) {
        case 'banner':
            state.modelName = msg.model || '';
            state.workspace = msg.workspace || '';
            state.version = msg.version || '';
            state.sessionId = msg.session_id || '';
            updateTopbar();
            updateStatusBar();
            loadSessions();
            break;
        case 'token':
            appendAssistantToken(state, elements.msgEl, msg.content || '');
            break;
        case 'tool_call_start':
            finishAssistant(state);
            addToolRun(msg.tool_name, msg.tool_args);
            break;
        case 'tool_call_result':
            finishToolRun(msg.tool_name, msg.tool_result || msg.content);
            break;
        case 'approval_required':
            finishAssistant(state);
            break;
        case 'done':
            finishAssistant(state);
            if (msg.usage) {
                state.totalTokens = msg.usage;
                updateStatusBar();
            }
            state.turnCount += 1;
            break;
        case 'error':
            finishAssistant(state);
            break;
    }
    if (nextStatus) setStatus(nextStatus);
    scrollBottom();
}

function addToolRun(name, args) {
    const run = toolRunStore.start(name, args);
    const controller = createToolPanel(run, { setStatus });
    toolPanels.set(run.id, controller);
    elements.msgEl.appendChild(controller.element);
}

function finishToolRun(name, result) {
    const run = toolRunStore.finish(name, result);
    let controller = toolPanels.get(run.id);
    if (!controller) {
        controller = createToolPanel(run, { setStatus });
        toolPanels.set(run.id, controller);
        elements.msgEl.appendChild(controller.element);
        return;
    }
    controller.update(run);
}

function send() {
    const text = elements.inputEl.value;
    if (!text.trim() || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
    const trimmed = text.trim();
    const lowered = trimmed.toLowerCase();

    if (trimmed.startsWith('/') || ['exit', 'quit', ':q'].includes(lowered)) {
        handleSlash(trimmed, slashContext());
        elements.inputEl.value = '';
        return;
    }

    appendUserMessage(elements.msgEl, text);
    state.ws.send(text);
    elements.inputEl.value = '';
    elements.inputEl.style.height = '';
    setStatus('思考中...');
}

async function loadSessions() {
    try {
        state.sessions = await fetchJson('/sessions');
    } catch (e) {
        state.sessions = [];
    }
    renderSessionList();
}

function renderSessionList() {
    elements.sessionListEl.replaceChildren();
    if (state.sessions.length === 0) {
        elements.sessionListEl.append(el('div', { className: 'empty-state', text: '暂无会话' }));
        return;
    }
    state.sessions.forEach(session => {
        const active = isActiveSession(session.id) ? ' active' : '';
        const item = el('div', { className: 'session-item' + active });
        item.dataset.sid = session.id;
        item.addEventListener('click', () => switchSession(session.id));
        const meta = el('div', { className: 'sess-meta' });
        meta.append(
            el('span', { text: session.model || '-' }),
            el('span', { text: relativeTime(session.updated_at) }),
        );
        item.append(
            el('div', { className: 'sess-title', text: session.title || '未命名' }),
            meta,
        );
        elements.sessionListEl.append(item);
    });
}

function isActiveSession(candidateId) {
    return Boolean(state.sessionId)
        && (candidateId === state.sessionId || candidateId.startsWith(state.sessionId));
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
    if (targetId === state.sessionId) return;
    const oldSocket = state.ws;
    clearMessages();
    resetConversationState();
    state.sessionId = targetId;
    renderSessionList();
    updateStatusBar();
    setStatus('切换会话中...');
    connect(targetId);
    disconnectChat(oldSocket);
}

async function newChat() {
    try {
        const created = await postJson('/sessions', { title: '新会话' });
        setStatus('已创建新会话');
        await loadSessions();
        switchSession(created.id);
    } catch (e) {
        setStatus('创建失败：' + e.message);
    }
}

function updateStatusBar() {
    elements.sbModel.textContent = state.modelName || '-';
    elements.sbWorkspace.textContent = state.workspace || '-';
    elements.sbTokens.textContent = (state.totalTokens.total || 0).toLocaleString();
}

function updateTopbar() {
    elements.topbarTitle.textContent = state.sessionId ? state.sessionId.slice(0, 8) : 'easy-claw';
}

function downloadMarkdown() {
    exportMarkdown({
        msgEl: elements.msgEl,
        state,
        setStatus,
    });
}

function slashContext() {
    return {
        state,
        setStatus,
        clearMessages,
        showModal,
        switchSession,
        disconnect,
        downloadMarkdown,
    };
}

elements.inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
    }
});

elements.inputEl.addEventListener('input', () => {
    elements.inputEl.style.height = '';
    elements.inputEl.style.height = Math.min(elements.inputEl.scrollHeight, 160) + 'px';
});

elements.sendBtn.addEventListener('click', send);
elements.newChatBtn.addEventListener('click', newChat);
elements.modalOverlay.addEventListener('click', e => {
    if (e.target === elements.modalOverlay) closeModal();
});
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
});

connect();
loadSessions();

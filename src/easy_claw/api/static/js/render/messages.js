import { el } from '../dom.js';
import { renderMarkdown } from '../markdown.js';

export function clearMessages(state, msgEl, toolRunStore = null, toolPanels = null) {
    msgEl.replaceChildren();
    state.currentAssistant = null;
    state.currentAssistantRaw = '';
    if (toolRunStore) toolRunStore.clear();
    if (toolPanels) toolPanels.clear();
}

export function appendUserMessage(msgEl, text) {
    const userMsg = el('div', { className: 'message user', text });
    msgEl.appendChild(userMsg);
}

export function appendAssistantToken(state, msgEl, text) {
    if (!state.currentAssistant) {
        state.currentAssistant = el('div', { className: 'message assistant markdown-body' });
        state.currentAssistantRaw = '';
        state.currentAssistant.append(el('span', { className: 'cursor' }));
        msgEl.appendChild(state.currentAssistant);
    }
    const cursor = state.currentAssistant.querySelector('.cursor');
    cursor.before(document.createTextNode(text));
    state.currentAssistantRaw += text;
}

export function finishAssistant(state) {
    const node = state.currentAssistant;
    if (!node) return;

    const raw = state.currentAssistantRaw;
    const cursor = node.querySelector('.cursor');
    if (cursor) cursor.remove();
    node.replaceChildren(renderMarkdown(raw));
    state.currentAssistant = null;
    state.currentAssistantRaw = '';
}

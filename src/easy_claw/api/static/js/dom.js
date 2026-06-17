export const elements = {
    msgEl: document.getElementById('messages'),
    inputEl: document.getElementById('input'),
    sendBtn: document.getElementById('send-btn'),
    dotEl: document.getElementById('conn-dot'),
    topbarTitle: document.getElementById('topbar-title'),
    topbarStatus: document.getElementById('topbar-status'),
    modalOverlay: document.getElementById('modal-overlay'),
    modalContent: document.getElementById('modal-content'),
    sessionListEl: document.getElementById('session-list'),
    newChatBtn: document.getElementById('new-chat-btn'),
    sbModel: document.getElementById('sb-model'),
    sbWorkspace: document.getElementById('sb-workspace'),
    sbTokens: document.getElementById('sb-tokens'),
};

export function el(tag, options = {}, children = []) {
    const node = document.createElement(tag);
    if (options.className) node.className = options.className;
    if (options.text !== undefined) node.textContent = String(options.text);
    if (options.style) Object.assign(node.style, options.style);
    for (const child of children) {
        node.append(child);
    }
    return node;
}

export function scrollBottom() {
    elements.msgEl.scrollTop = elements.msgEl.scrollHeight;
}

import { el, elements } from './dom.js';

export function heading(text) {
    return el('h2', { text });
}

export function infoText(text) {
    return el(
        'p',
        {
            text,
            style: { marginTop: '12px', fontSize: '13px', color: 'var(--dim)' },
        },
    );
}

export function tableFromRows(rows) {
    const table = el('table');
    rows.forEach(([label, value]) => {
        const row = el('tr');
        row.append(el('td', { text: label }), el('td', { text: value }));
        table.append(row);
    });
    return table;
}

export function showModal(...nodes) {
    const closeButton = el('button', { className: 'close', text: '关闭' });
    closeButton.addEventListener('click', closeModal);
    elements.modalContent.replaceChildren(...nodes, closeButton);
    elements.modalOverlay.classList.add('show');
}

export function closeModal() {
    elements.modalOverlay.classList.remove('show');
}

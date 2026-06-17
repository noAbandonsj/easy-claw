export function downloadMarkdown({ msgEl, state, setStatus }) {
    const parts = ['# easy-claw 对话记录\n',
        '\n- **会话：** `' + state.sessionId + '`',
        '- **模型：** ' + state.modelName,
        '- **工作区：** ' + state.workspace,
        '- **导出时间：** ' + new Date().toISOString().replace('T', ' ').slice(0, 19),
        '\n---\n'];
    const children = msgEl.children;
    for (let i = 0; i < children.length; i++) {
        const node = children[i];
        if (node.classList.contains('message')) {
            const role = node.classList.contains('user') ? '**用户：**' : '**easy-claw：**';
            parts.push('\n' + role + '\n\n' + node.textContent + '\n');
        } else if (node.classList.contains('tool-panel')) {
            const header = node.querySelector('.header')?.textContent || '工具';
            const body = node.querySelector('.body')?.textContent || '';
            parts.push('\n> ' + header + '\n> \n> ' + body.replace(/\n/g, '\n> ') + '\n');
        }
    }
    const blob = new Blob([parts.join('\n')], { type: 'text/markdown' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'easy-claw-' + state.sessionId + '.md';
    link.click();
    setStatus('对话记录已下载');
}

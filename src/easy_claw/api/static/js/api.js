let slashCommands = null;

export async function loadSlashCommands() {
    if (slashCommands) return slashCommands;
    const response = await fetch('/slash-commands');
    if (!response.ok) throw new Error('无法加载命令列表');
    slashCommands = await response.json();
    return slashCommands;
}

export async function fetchJson(path) {
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

export async function postJson(path, body) {
    const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
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

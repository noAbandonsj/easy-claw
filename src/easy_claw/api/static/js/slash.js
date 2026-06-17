import { fetchJson, loadSlashCommands } from './api.js';
import { heading, infoText, tableFromRows } from './modal.js';

export async function handleSlash(cmd, context) {
    const parts = cmd.trim().split(/\s+/);
    const token = parts[0].toLowerCase();
    const args = parts.slice(1).join(' ');
    try {
        switch (token) {
        case '/help':
            await showCommandHelp(args, context);
            break;
        case '/clear':
            context.clearMessages();
            context.setStatus('已清空对话视图（服务端会话仍保留）');
            break;
        case '/status':
            showStatus(context);
            break;
        case '/save':
            context.downloadMarkdown();
            break;
        case '/skills':
            await showSkills(context);
            break;
        case '/mcp':
            await showMcp(context);
            break;
        case '/browser':
            await showBrowser(context);
            break;
        case '/sessions':
            await showSessions(context);
            break;
        case '/resume':
            await resumeSession(args, context);
            break;
        case '/exit':
        case '/quit':
        case 'exit':
        case 'quit':
        case ':q':
            context.setStatus('已断开连接');
            context.disconnect();
            break;
        default:
            if (['/workspace', '/model', '/doctor', '/delete-session'].includes(token)) {
                context.setStatus(token + ' 目前仅支持 CLI。请使用 uv run easy-claw。');
            } else {
                context.setStatus('未知命令：' + cmd);
            }
        }
    } catch (e) {
        context.setStatus('命令执行失败：' + e.message);
    }
}

async function showCommandHelp(commandName, context) {
    const commands = await loadSlashCommands();
    if (commandName) {
        let normalized = commandName.trim().toLowerCase();
        if (normalized && !normalized.startsWith('/') && !['exit', 'quit', ':q'].includes(normalized)) {
            normalized = '/' + normalized;
        }
        const command = commands.find(c => c.name === normalized || (c.aliases || []).includes(normalized));
        if (!command) {
            context.setStatus('未知命令：' + commandName);
            return;
        }
        context.showModal(
            heading(command.usage),
            tableFromRows([
                ['类别', command.group],
                ['说明', command.description],
                ['别名', (command.aliases || []).join(', ') || '-'],
            ]),
        );
        return;
    }
    context.showModal(
        heading('聊天内斜杠命令'),
        tableFromRows(commands.map(c => [c.usage, c.description])),
        infoText('命令定义来自 CLI slash registry；部分配置类命令在网页端仅显示提示。'),
    );
}

function showStatus(context) {
    const current = context.state;
    context.showModal(
        heading('会话状态'),
        tableFromRows([
            ['模型', current.modelName],
            ['工作区', current.workspace],
            ['版本', current.version],
            ['会话', current.sessionId],
            ['轮次', String(current.turnCount)],
            ['Token', (current.totalTokens.total || 0).toLocaleString()],
        ]),
    );
}

async function showSkills(context) {
    const payload = await fetchJson('/skills');
    const rows = payload.sources.map(source => [
        source.label,
        source.skill_count + ' 个 | ' + source.backend_path + ' | ' + source.filesystem_path,
    ]);
    context.showModal(
        heading('Skill 来源'),
        tableFromRows(rows.length ? rows : [['无', '没有找到 skill 来源']]),
        infoText('共 ' + payload.source_count + ' 个来源，' + payload.skill_count + ' 个 skill。'),
    );
}

async function showMcp(context) {
    const payload = await fetchJson('/mcp');
    context.showModal(
        heading('MCP'),
        tableFromRows([
            ['模式', payload.mode],
            ['状态', payload.status],
            ['配置', payload.config_path],
            ['服务数', payload.server_count],
        ]),
    );
}

async function showBrowser(context) {
    const payload = await fetchJson('/browser');
    context.showModal(
        heading('浏览器工具'),
        tableFromRows([
            ['启用', yesNo(payload.enabled)],
            ['无头模式', yesNo(payload.headless)],
            ['Chromium', yesNo(payload.chromium_installed)],
            ['Headless', yesNo(payload.chromium_headless_installed)],
        ]),
    );
}

async function showSessions(context) {
    const sessions = await fetchJson('/sessions');
    const rows = sessions.map(session => [
        session.id.slice(0, 8),
        session.title + ' | ' + (session.model || '-') + ' | ' + session.updated_at.slice(0, 19),
    ]);
    context.showModal(
        heading('历史会话'),
        tableFromRows(rows.length ? rows : [['无', '没有找到会话']]),
        infoText('使用 /resume <session-id> 可按前缀恢复。'),
    );
}

async function resumeSession(sessionPrefix, context) {
    if (!sessionPrefix) {
        context.setStatus('用法：/resume <session-id>');
        return;
    }
    const session = await fetchJson('/sessions/resolve/' + encodeURIComponent(sessionPrefix));
    context.switchSession(session.id);
}

function yesNo(value) {
    return value ? '是' : '否';
}

import { el } from '../dom.js';
import {
    copyToolPayload,
    describeTool,
    formatContent,
    summarizeToolPayload,
    summarizeToolResult,
} from '../tools.js';

export function createToolPanel(run, options = {}) {
    let currentRun = run;
    const setStatus = options.setStatus || (() => {});
    const panel = el('div', { className: panelClass(currentRun) });
    panel.dataset.toolRunId = currentRun.id;

    const header = el('button', { className: 'header call' });
    header.type = 'button';
    const summary = el('div', { className: 'tool-summary' });
    const actions = el('div', { className: 'tool-actions' });
    const body = el('div', { className: 'body' });

    header.addEventListener('click', () => togglePanel(panel));
    panel.append(header, summary, actions, body);

    function render() {
        panel.className = panelClass(currentRun);
        const isFinished = currentRun.status === 'finished';
        const descriptor = describeTool(currentRun.name);
        header.className = 'header ' + (isFinished ? 'result' : 'call');
        header.replaceChildren(buildTitle(descriptor, isFinished), el('span', {
            className: 'arrow',
            text: '\u25b6',
        }));

        summary.replaceChildren(...summaryRows(currentRun).map(([label, value]) => {
            const row = el('div', { className: 'tool-summary-row' });
            row.append(
                el('span', { className: 'tool-summary-key', text: label }),
                el('span', { className: 'tool-summary-value', text: value }),
            );
            return row;
        }));

        actions.replaceChildren(...buildActions(currentRun, panel, setStatus));
        body.replaceChildren(...detailSections(currentRun));
    }

    render();

    return {
        element: panel,
        update(nextRun) {
            currentRun = nextRun;
            render();
        },
    };
}

function buildTitle(descriptor, isFinished) {
    const title = el('span', { className: 'tool-title-block' });
    const meta = el('span', { className: 'tool-meta' });
    meta.append(
        el('span', { className: 'tool-badge', text: descriptor.category }),
        el('span', { className: 'tool-phase', text: isFinished ? '完成' : '运行中' }),
    );
    title.append(
        meta,
        el('span', { className: 'tool-name', text: descriptor.name }),
        el('span', { className: 'tool-explanation', text: descriptor.explanation }),
    );
    return title;
}

function summaryRows(run) {
    if (run.status === 'finished') {
        return [
            ['状态', '已完成'],
            ...summarizeToolResult(run.result),
        ];
    }
    return [
        ['状态', '运行中'],
        ...summarizeToolPayload(run.args),
    ];
}

function buildActions(run, panel, setStatus) {
    const expandButton = el('button', {
        className: 'tool-action tool-expand',
        text: panel.classList.contains('open') ? '收起详情' : '展开详情',
    });
    expandButton.type = 'button';
    expandButton.addEventListener('click', () => togglePanel(panel));

    const copyArgsButton = el('button', { className: 'tool-action', text: '复制参数' });
    copyArgsButton.type = 'button';
    copyArgsButton.addEventListener('click', () => {
        copyToolPayload('复制参数', formatContent(run.args), setStatus);
    });

    const buttons = [expandButton, copyArgsButton];
    if (run.status === 'finished') {
        const copyResultButton = el('button', { className: 'tool-action', text: '复制结果' });
        copyResultButton.type = 'button';
        copyResultButton.addEventListener('click', () => {
            copyToolPayload('复制结果', formatContent(run.result), setStatus);
        });
        buttons.push(copyResultButton);
    }
    return buttons;
}

function detailSections(run) {
    const sections = [
        detailSection('参数', formatContent(run.args)),
    ];
    if (run.status === 'finished') {
        sections.push(detailSection('结果', formatContent(run.result)));
    }
    return sections;
}

function detailSection(title, content) {
    const section = el('div', { className: 'tool-detail-section' });
    section.append(
        el('div', { className: 'tool-detail-title', text: title }),
        el('pre', { className: 'tool-detail-body', text: content }),
    );
    return section;
}

function panelClass(run) {
    const phase = run.status === 'finished' ? 'result finished' : 'call running';
    return 'tool-panel ' + phase;
}

function togglePanel(panel) {
    panel.classList.toggle('open');
    const expandButton = panel.querySelector('.tool-expand');
    if (expandButton) {
        expandButton.textContent = panel.classList.contains('open') ? '收起详情' : '展开详情';
    }
}

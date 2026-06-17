export const TOOL_SUMMARY_KEYS = [
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

export class ToolRunStore {
    constructor() {
        this.nextId = 1;
        this.runs = [];
        this.pending = [];
    }

    start(name, args) {
        const run = {
            id: String(this.nextId),
            name: normalizedToolName(name),
            args,
            result: null,
            status: 'running',
        };
        this.nextId += 1;
        this.runs.push(run);
        this.pending.push(run);
        return run;
    }

    finish(name, result) {
        const toolName = normalizedToolName(name);
        let run = [...this.pending].reverse().find(item => item.name === toolName);
        if (!run) {
            run = this.start(toolName, null);
        }
        run.status = 'finished';
        run.result = result;
        this.pending = this.pending.filter(item => item !== run);
        return run;
    }

    pendingCount() {
        return this.pending.length;
    }

    clear() {
        this.nextId = 1;
        this.runs = [];
        this.pending = [];
    }
}

export function normalizedToolName(name) {
    return name ? String(name) : '未知工具';
}

export function describeTool(name) {
    const toolName = normalizedToolName(name);
    const lowered = toolName.toLowerCase();
    const descriptor = TOOL_DESCRIPTORS.find(item => (
        item.keys.some(key => lowered.includes(key))
    ));
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

export function isPlainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function shortenText(text, limit = 180) {
    const normalized = String(text || '').replace(/\s+/g, ' ').trim();
    if (normalized.length <= limit) return normalized;
    return normalized.slice(0, limit - 1) + '…';
}

export function previewValue(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return shortenText(value, 140);
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) return '[' + value.length + ' 项] ' + shortenText(formatContent(value), 120);
    if (isPlainObject(value)) return shortenText(formatContent(value), 120);
    return shortenText(String(value), 120);
}

export function summarizeObjectFields(value, keys) {
    const rows = [];
    if (!isPlainObject(value)) return rows;
    keys.forEach(key => {
        if (Object.prototype.hasOwnProperty.call(value, key)) {
            rows.push([key, previewValue(value[key])]);
        }
    });
    return rows;
}

export function summarizeFirstLevel(value) {
    if (!isPlainObject(value)) {
        const preview = previewValue(value);
        return preview ? [['内容', preview]] : [['内容', '空']];
    }
    const rows = Object.entries(value)
        .slice(0, 4)
        .map(([key, val]) => [key, previewValue(val)]);
    return rows.length ? rows : [['内容', '空对象']];
}

export function summarizeToolPayload(value) {
    const rows = summarizeObjectFields(value, TOOL_SUMMARY_KEYS);
    return rows.length ? rows : summarizeFirstLevel(value);
}

export function summarizeToolResult(value) {
    const formatted = formatContent(value);
    const lengthLabel = formatted.length.toLocaleString() + ' 字符';
    const preview = shortenText(formatted, 220);
    return [
        ['摘要', preview || '空结果'],
        ['长度', lengthLabel],
    ];
}

export function formatContent(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    try {
        return JSON.stringify(val, null, 2);
    } catch (e) {
        return String(val);
    }
}

export async function copyToolPayload(label, content, setStatus = () => {}) {
    try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
            throw new Error('浏览器不支持剪贴板写入');
        }
        await navigator.clipboard.writeText(content);
        setStatus(label + '已复制');
    } catch (e) {
        setStatus(label + '失败：无法写入剪贴板');
    }
}

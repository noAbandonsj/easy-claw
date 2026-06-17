export function statusForStreamEvent(msg) {
    switch (msg.type) {
        case 'banner':
            return '就绪';
        case 'token':
            return '回复中...';
        case 'tool_call_start':
            return '调用工具：' + (msg.tool_name || '未知');
        case 'tool_call_result':
            return '整理回复...';
        case 'approval_required':
            return '工具执行需要确认（已自动批准）';
        case 'done':
            return '就绪';
        case 'error':
            return '错误：' + msg.content;
        default:
            return null;
    }
}

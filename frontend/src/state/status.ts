import type { StreamEvent } from '../api/types';

export function statusForEvent(event: StreamEvent): string {
  switch (event.type) {
    case 'banner':
      return '已连接';
    case 'token':
      return '回复中...';
    case 'tool_call_start':
      return '调用工具...';
    case 'tool_call_result':
      return '整理回复...';
    case 'approval_required':
      return '等待审批...';
    case 'done':
      return '就绪';
    case 'error':
      return '出错';
    case 'interrupted':
      return '已中断';
    default:
      return '就绪';
  }
}

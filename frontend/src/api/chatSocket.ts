import type { ClientMessage } from './types';

export function buildChatSocketUrl(
  sessionId?: string | null,
  baseUrl: URL = new URL(window.location.href),
): string {
  const protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = new URL('/ws/chat', `${protocol}//${baseUrl.host}`);
  if (sessionId) {
    url.searchParams.set('session_id', sessionId);
  }
  return url.toString();
}

export function serializePrompt(content: string): string {
  return JSON.stringify({ type: 'prompt', content } satisfies ClientMessage);
}

export function serializeApprovalDecision(
  approvalId: string,
  decision: 'approve' | 'reject',
): string {
  return JSON.stringify({
    type: 'approval_decision',
    approval_id: approvalId,
    approve: decision === 'approve',
  } satisfies ClientMessage);
}

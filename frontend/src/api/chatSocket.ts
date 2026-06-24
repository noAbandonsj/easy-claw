import type { ClientMessage } from './types';

export function buildChatSocketUrl(
  sessionId?: string | null,
  baseUrl: URL = new URL(window.location.href),
  overrides: { model?: string | null; workspacePath?: string | null } = {},
): string {
  const protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = new URL('/ws/chat', `${protocol}//${baseUrl.host}`);
  if (sessionId) {
    url.searchParams.set('session_id', sessionId);
  }
  if (overrides.workspacePath) {
    url.searchParams.set('workspace_path', overrides.workspacePath);
  }
  if (overrides.model) {
    url.searchParams.set('model', overrides.model);
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

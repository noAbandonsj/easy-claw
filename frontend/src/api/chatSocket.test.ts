import { describe, expect, it } from 'vitest';
import { buildChatSocketUrl, serializeApprovalDecision, serializePrompt } from './chatSocket';

describe('chatSocket helpers', () => {
  it('builds a websocket URL for the active session', () => {
    const url = buildChatSocketUrl(
      'session-1',
      new URL('http://127.0.0.1:5173/app/sessions'),
    );

    expect(url).toBe('ws://127.0.0.1:5173/ws/chat?session_id=session-1');
  });

  it('serializes structured prompt and approval messages', () => {
    expect(serializePrompt('你好')).toBe(JSON.stringify({ type: 'prompt', content: '你好' }));
    expect(serializeApprovalDecision('approval-1', 'reject')).toBe(
      JSON.stringify({
        type: 'approval_decision',
        approval_id: 'approval-1',
        approve: false,
      }),
    );
  });
});

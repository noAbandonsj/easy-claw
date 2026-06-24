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

  it('includes web workspace and model overrides in the websocket URL', () => {
    const url = buildChatSocketUrl(
      'session-1',
      new URL('http://127.0.0.1:5173/app'),
      {
        model: 'web-model',
        workspacePath: 'D:/workspace',
      },
    );

    expect(url).toBe(
      'ws://127.0.0.1:5173/ws/chat?session_id=session-1&workspace_path=D%3A%2Fworkspace&model=web-model',
    );
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

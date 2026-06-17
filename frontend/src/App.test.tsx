import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

class MockWebSocket {
  static CLOSED = 3;
  static CONNECTING = 0;
  static OPEN = 1;

  onclose: (() => void) | null = null;
  onopen: (() => void) | null = null;
  readyState = MockWebSocket.CONNECTING;

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  send() {}
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads sessions into the React chat shell', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: 'session-1',
            title: '网页聊天',
            workspace_path: 'D:/workspace',
            model: 'deepseek-v4-pro',
            created_at: '2026-06-17T00:00:00+00:00',
            updated_at: '2026-06-17T00:00:00+00:00',
          },
        ],
      }),
    );

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Easy Claw' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /网页聊天/ })).toBeInTheDocument();
    expect(screen.getByLabelText('消息')).toBeDisabled();
  });
});

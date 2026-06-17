import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useChatSocket } from './useChatSocket';

class MockWebSocket {
  static CLOSED = 3;
  static CONNECTING = 0;
  static instances: MockWebSocket[] = [];
  static OPEN = 1;

  onclose: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onopen: (() => void) | null = null;
  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  url: string;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  receive(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  send(payload: string) {
    this.sent.push(payload);
  }
}

describe('useChatSocket', () => {
  afterEach(() => {
    MockWebSocket.instances = [];
    vi.unstubAllGlobals();
  });

  it('sends prompts and reduces streamed events into message blocks', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket);

    const { result } = renderHook(() => useChatSocket('session-1'));

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];

    act(() => socket.open());
    act(() => {
      result.current.sendPrompt('你好');
    });
    act(() => {
      socket.receive({ type: 'token', content: '收到' });
      socket.receive({ type: 'done' });
    });

    expect(socket.sent).toEqual([JSON.stringify({ type: 'prompt', content: '你好' })]);
    expect(result.current.status).toBe('就绪');
    expect(result.current.blocks).toEqual([
      { id: 'user-1', kind: 'user', content: '你好' },
      { id: 'assistant-1', kind: 'assistant', content: '收到', streaming: false },
    ]);
  });
});

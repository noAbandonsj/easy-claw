import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

class MockWebSocket {
  static CLOSED = 3;
  static CONNECTING = 0;
  static OPEN = 1;

  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  readyState = MockWebSocket.CONNECTING;
  url: string;

  static instances: MockWebSocket[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.();
    });
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  send() {}
}

describe('App', () => {
  afterEach(() => {
    MockWebSocket.instances = [];
    vi.unstubAllGlobals();
  });

  it('loads sessions into the runbook cockpit shell', async () => {
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
    expect(await screen.findByRole('button', { name: /^网页聊天/ })).toBeInTheDocument();
    expect(screen.getByLabelText('运行上下文')).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: '运行检查器' })).toBeInTheDocument();
    expect(within(screen.getByLabelText('运行上下文')).getByText('D:/workspace')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText('消息')).not.toBeDisabled());
  });

  it('opens doctor details from the slash command', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === '/sessions') {
          return {
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
          };
        }
        if (path === '/doctor') {
          return {
            ok: true,
            json: async () => ({
              api_key_configured: true,
              approval_mode: 'permissive',
              base_url: 'https://api.example.com',
              browser: {
                chromium_headless_installed: false,
                chromium_installed: true,
                enabled: false,
                headless: false,
              },
              checkpoint_db_path: 'D:/repo/data/checkpoints.sqlite',
              data_dir: 'D:/repo/data',
              execution_mode: 'local',
              mcp_config_path: 'mcp_servers.json',
              mcp_mode: 'disabled',
              mcp_status: '已关闭',
              model: 'deepseek-v4-pro',
              product_db_path: 'D:/repo/data/easy-claw.db',
              version: '0.5.0',
              workspace: 'D:/workspace',
            }),
          };
        }
        throw new Error(`unexpected fetch ${path}`);
      }),
    );

    render(<App />);

    const input = await screen.findByLabelText('消息');
    await waitFor(() => expect(input).not.toBeDisabled());
    fireEvent.change(input, { target: { value: '/doctor' } });
    fireEvent.click(screen.getByRole('button', { name: '执行' }));

    expect(await screen.findByRole('heading', { name: '本地诊断' })).toBeInTheDocument();
    expect(screen.getAllByText('deepseek-v4-pro').length).toBeGreaterThan(0);
  });

  it('deletes a session from the sidebar', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === '/sessions' && !init) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'session-1',
              title: '第一会话',
              workspace_path: 'D:/workspace',
              model: 'deepseek-v4-pro',
              created_at: '2026-06-17T00:00:00+00:00',
              updated_at: '2026-06-17T00:00:00+00:00',
            },
            {
              id: 'session-2',
              title: '第二会话',
              workspace_path: 'D:/workspace',
              model: 'deepseek-v4-pro',
              created_at: '2026-06-17T00:00:00+00:00',
              updated_at: '2026-06-17T00:00:00+00:00',
            },
          ],
        };
      }
      if (path === '/sessions/session-1' && init?.method === 'DELETE') {
        return {
          ok: true,
          json: async () => ({ deleted: true, session: { id: 'session-1' } }),
        };
      }
      throw new Error(`unexpected fetch ${path}`);
    });
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);

    expect(await screen.findByRole('button', { name: /^第一会话/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '删除会话 第一会话' }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/sessions/session-1', { method: 'DELETE' }),
    );
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /^第一会话/ })).not.toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^第二会话/ })).toHaveAttribute(
        'aria-current',
        'true',
      ),
    );
  });
});

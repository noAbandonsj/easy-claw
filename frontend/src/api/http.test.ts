import { afterEach, describe, expect, it, vi } from 'vitest';
import { createSession, listSessions } from './http';

describe('http client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads sessions from the backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: 'session-1',
          title: 'Web chat',
          workspace_path: 'D:/workspace',
          model: 'deepseek-v4-pro',
          created_at: '2026-06-17T00:00:00+00:00',
          updated_at: '2026-06-17T00:00:00+00:00',
        },
      ],
    });
    vi.stubGlobal('fetch', fetchMock);

    const sessions = await listSessions();

    expect(fetchMock).toHaveBeenCalledWith('/sessions');
    expect(sessions[0].id).toBe('session-1');
  });

  it('creates a web session with JSON payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'session-2',
        title: '网页聊天',
        workspace_path: 'D:/workspace',
        model: 'deepseek-v4-pro',
        created_at: '2026-06-17T00:00:00+00:00',
        updated_at: '2026-06-17T00:00:00+00:00',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const session = await createSession('网页聊天');

    expect(fetchMock).toHaveBeenCalledWith('/sessions', {
      body: JSON.stringify({ title: '网页聊天' }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
    expect(session.id).toBe('session-2');
  });
});

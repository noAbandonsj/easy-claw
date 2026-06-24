import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createSession,
  deleteSession,
  fetchDoctor,
  listSessions,
  resolveWorkspace,
  saveConversation,
} from './http';

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

  it('deletes a session by id or prefix', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ deleted: true, session: { id: 'session-1' } }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await deleteSession('session-1');

    expect(fetchMock).toHaveBeenCalledWith('/sessions/session-1', { method: 'DELETE' });
    expect(result.deleted).toBe(true);
  });

  it('loads doctor details from the backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ model: 'deepseek-v4-pro', workspace: 'D:/workspace' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await fetchDoctor();

    expect(fetchMock).toHaveBeenCalledWith('/doctor');
    expect(result.model).toBe('deepseek-v4-pro');
  });

  it('resolves a workspace path through the backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ workspace_path: 'D:/workspace' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await resolveWorkspace('D:/workspace');

    expect(fetchMock).toHaveBeenCalledWith('/workspace/resolve', {
      body: JSON.stringify({ path: 'D:/workspace' }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
    expect(result.workspace_path).toBe('D:/workspace');
  });

  it('saves visible conversation messages through the backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ path: 'D:/tmp/chat.md', saved: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await saveConversation({
      messages: [{ kind: 'user', content: '你好' }],
      model: 'deepseek-v4-pro',
      path: 'D:/tmp/chat.md',
      session_id: 'session-1',
      workspace_path: 'D:/workspace',
    });

    expect(fetchMock).toHaveBeenCalledWith('/conversation/save', {
      body: JSON.stringify({
        messages: [{ kind: 'user', content: '你好' }],
        model: 'deepseek-v4-pro',
        path: 'D:/tmp/chat.md',
        session_id: 'session-1',
        workspace_path: 'D:/workspace',
      }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
    expect(result.saved).toBe(true);
  });
});

import type {
  BrowserPayload,
  McpPayload,
  SessionRecord,
  SkillsPayload,
  SlashCommandSpec,
} from './types';

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = init ? await fetch(path, init) : await fetch(path);
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return (await response.json()) as T;
}

export function listSessions(): Promise<SessionRecord[]> {
  return requestJson<SessionRecord[]>('/sessions');
}

export function createSession(title = '网页聊天'): Promise<SessionRecord> {
  return requestJson<SessionRecord>('/sessions', {
    body: JSON.stringify({ title }),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  });
}

export function resolveSession(sessionId: string): Promise<SessionRecord> {
  return requestJson<SessionRecord>(`/sessions/resolve/${encodeURIComponent(sessionId)}`);
}

export function fetchSkills(): Promise<SkillsPayload> {
  return requestJson<SkillsPayload>('/skills');
}

export function fetchMcp(): Promise<McpPayload> {
  return requestJson<McpPayload>('/mcp');
}

export function fetchBrowser(): Promise<BrowserPayload> {
  return requestJson<BrowserPayload>('/browser');
}

export function fetchSlashCommands(): Promise<SlashCommandSpec[]> {
  return requestJson<SlashCommandSpec[]>('/slash-commands');
}

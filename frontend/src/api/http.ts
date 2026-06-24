import type {
  BrowserPayload,
  DeleteSessionPayload,
  DoctorPayload,
  McpPayload,
  SaveConversationPayload,
  SaveConversationResponse,
  SessionRecord,
  SkillsPayload,
  SlashCommandSpec,
  WorkspacePayload,
} from './types';

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = init ? await fetch(path, init) : await fetch(path);
  if (!response.ok) {
    let detail: string;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ? `：${payload.detail}` : '';
    } catch {
      detail = '';
    }
    throw new Error(`请求失败：${response.status}${detail}`);
  }
  return (await response.json()) as T;
}

function jsonRequest<T>(path: string, body: object): Promise<T> {
  return requestJson<T>(path, {
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  });
}

export function listSessions(): Promise<SessionRecord[]> {
  return requestJson<SessionRecord[]>('/sessions');
}

export function createSession(
  title = '网页聊天',
  options: { model?: string | null; workspace_path?: string | null } = {},
): Promise<SessionRecord> {
  return jsonRequest<SessionRecord>('/sessions', {
    title,
    ...(options.workspace_path ? { workspace_path: options.workspace_path } : {}),
    ...(options.model ? { model: options.model } : {}),
  });
}

export function resolveSession(sessionId: string): Promise<SessionRecord> {
  return requestJson<SessionRecord>(`/sessions/resolve/${encodeURIComponent(sessionId)}`);
}

export function deleteSession(sessionId: string): Promise<DeleteSessionPayload> {
  return requestJson<DeleteSessionPayload>(`/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  });
}

export function resolveWorkspace(path: string): Promise<WorkspacePayload> {
  return jsonRequest<WorkspacePayload>('/workspace/resolve', { path });
}

export function saveConversation(
  payload: SaveConversationPayload,
): Promise<SaveConversationResponse> {
  return jsonRequest<SaveConversationResponse>('/conversation/save', payload);
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

export function fetchDoctor(): Promise<DoctorPayload> {
  return requestJson<DoctorPayload>('/doctor');
}

export function fetchSlashCommands(): Promise<SlashCommandSpec[]> {
  return requestJson<SlashCommandSpec[]>('/slash-commands');
}

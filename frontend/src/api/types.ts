export type TokenUsage = {
  input?: number;
  output?: number;
  total?: number;
};

export type ToolActionRequest = {
  name: string;
  args?: unknown;
  description?: string;
};

export type StreamEvent =
  | {
      type: 'banner';
      model?: string;
      workspace?: string;
      version?: string;
      session_id?: string;
    }
  | { type: 'token'; content: string }
  | { type: 'tool_call_start'; tool_name?: string; tool_args?: unknown; startedAt?: number }
  | {
      type: 'tool_call_result';
      tool_name?: string;
      tool_result?: unknown;
      content?: string;
      finishedAt?: number;
    }
  | {
      type: 'approval_required';
      approval_id?: string;
      approval_actions?: ToolActionRequest[];
    }
  | { type: 'done'; usage?: TokenUsage; content?: string }
  | { type: 'error'; content?: string }
  | { type: 'interrupted'; content?: string };

export type ClientMessage =
  | { type: 'prompt'; content: string }
  | { type: 'approval_decision'; approval_id: string; approve: boolean; message?: string };

export type SessionRecord = {
  id: string;
  title: string;
  workspace_path: string;
  model: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkspacePayload = {
  workspace_path: string;
};

export type DeleteSessionPayload = {
  deleted: boolean;
  session: SessionRecord;
};

export type SkillSource = {
  scope: string;
  label: string;
  skill_count: number;
  backend_path: string;
  filesystem_path: string;
};

export type SkillsPayload = {
  sources: SkillSource[];
  source_count: number;
  skill_count: number;
};

export type McpPayload = {
  mode: string;
  enabled: boolean;
  config_path: string;
  server_count: number;
  status: string;
};

export type BrowserPayload = {
  enabled: boolean;
  headless: boolean;
  chromium_installed: boolean;
  chromium_headless_installed: boolean;
};

export type DoctorPayload = {
  version: string;
  data_dir: string;
  product_db_path: string;
  checkpoint_db_path: string;
  workspace: string;
  model: string | null;
  base_url: string;
  api_key_configured: boolean;
  approval_mode: string;
  execution_mode: string;
  mcp_mode: string;
  mcp_config_path: string;
  mcp_status: string;
  mcp_server_count: number;
  max_model_calls: number | null;
  max_tool_calls: number | null;
  browser: BrowserPayload;
};

export type SaveConversationMessage = {
  kind: 'assistant' | 'user';
  content: string;
};

export type SaveConversationPayload = {
  path: string;
  session_id: string;
  messages: SaveConversationMessage[];
  workspace_path?: string;
  model?: string | null;
};

export type SaveConversationResponse = {
  saved: boolean;
  path: string;
};

export type SlashCommandSpec = {
  name: string;
  description: string;
  usage: string;
};

export type MessageBlock =
  | { id: string; kind: 'user'; content: string }
  | { id: string; kind: 'assistant'; content: string; streaming: boolean }
  | {
      id: string;
      kind: 'tool';
      name: string;
      args: unknown;
      result: unknown;
      status: 'running' | 'finished';
      startedAt?: number;
      finishedAt?: number;
    }
  | {
      id: string;
      kind: 'approval';
      approvalId: string;
      actions: ToolActionRequest[];
      status: 'pending' | 'approved' | 'rejected';
    }
  | { id: string; kind: 'error'; content: string };

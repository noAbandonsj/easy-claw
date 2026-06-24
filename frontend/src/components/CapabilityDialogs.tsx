import type {
  BrowserPayload,
  DoctorPayload,
  McpPayload,
  SessionRecord,
  SkillsPayload,
  SlashCommandSpec,
} from '../api/types';

export type CapabilityKind =
  | 'browser'
  | 'doctor'
  | 'help'
  | 'mcp'
  | 'sessions'
  | 'skills'
  | 'status';

type StatusPayload = {
  activeSessionId: string | null;
  model?: string | null;
  status: string;
  workspacePath?: string | null;
};

type CapabilityDialogProps =
  | { kind: 'browser'; payload: BrowserPayload }
  | { kind: 'doctor'; payload: DoctorPayload }
  | { kind: 'help'; payload: SlashCommandSpec[] }
  | { kind: 'mcp'; payload: McpPayload }
  | { kind: 'sessions'; payload: SessionRecord[] }
  | { kind: 'skills'; payload: SkillsPayload }
  | { kind: 'status'; payload: StatusPayload };

function yesNo(value: boolean): string {
  return value ? '是' : '否';
}

export function CapabilityDialog({ kind, payload }: CapabilityDialogProps) {
  if (kind === 'skills') {
    return (
      <section className="capability-dialog">
        <h2>Skill 来源</h2>
        <p>
          共 {payload.source_count} 个来源，{payload.skill_count} 个 Skill。
        </p>
        <table>
          <thead>
            <tr>
              <th>范围</th>
              <th>名称</th>
              <th>数量</th>
              <th>路径</th>
            </tr>
          </thead>
          <tbody>
            {payload.sources.map(source => (
              <tr key={`${source.scope}-${source.filesystem_path}`}>
                <td>{source.scope}</td>
                <td>{source.label}</td>
                <td>{source.skill_count}</td>
                <td>{source.filesystem_path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  }

  if (kind === 'mcp') {
    return (
      <section className="capability-dialog">
        <h2>MCP 状态</h2>
        <dl>
          <dt>模式</dt>
          <dd>{payload.mode}</dd>
          <dt>启用</dt>
          <dd>{yesNo(payload.enabled)}</dd>
          <dt>服务数</dt>
          <dd>{payload.server_count}</dd>
          <dt>配置</dt>
          <dd>{payload.config_path}</dd>
          <dt>状态</dt>
          <dd>{payload.status}</dd>
        </dl>
      </section>
    );
  }

  if (kind === 'browser') {
    return (
      <section className="capability-dialog">
        <h2>浏览器能力</h2>
        <dl>
          <dt>启用</dt>
          <dd>{yesNo(payload.enabled)}</dd>
          <dt>无头模式</dt>
          <dd>{yesNo(payload.headless)}</dd>
          <dt>Chromium</dt>
          <dd>{yesNo(payload.chromium_installed)}</dd>
          <dt>Headless Chromium</dt>
          <dd>{yesNo(payload.chromium_headless_installed)}</dd>
        </dl>
      </section>
    );
  }

  if (kind === 'doctor') {
    return (
      <section className="capability-dialog">
        <h2>本地诊断</h2>
        <dl>
          <dt>版本</dt>
          <dd>{payload.version}</dd>
          <dt>模型</dt>
          <dd>{payload.model || '未配置'}</dd>
          <dt>工作区</dt>
          <dd>{payload.workspace}</dd>
          <dt>数据目录</dt>
          <dd>{payload.data_dir}</dd>
          <dt>业务数据库</dt>
          <dd>{payload.product_db_path}</dd>
          <dt>检查点数据库</dt>
          <dd>{payload.checkpoint_db_path}</dd>
          <dt>模型服务</dt>
          <dd>{payload.base_url}</dd>
          <dt>密钥</dt>
          <dd>{payload.api_key_configured ? '已配置' : '未配置'}</dd>
          <dt>审批模式</dt>
          <dd>{payload.approval_mode}</dd>
          <dt>执行模式</dt>
          <dd>{payload.execution_mode}</dd>
          <dt>MCP</dt>
          <dd>{payload.mcp_status}</dd>
          <dt>MCP 配置</dt>
          <dd>{payload.mcp_config_path}</dd>
          <dt>浏览器工具</dt>
          <dd>{yesNo(payload.browser.enabled)}</dd>
          <dt>Chromium</dt>
          <dd>{yesNo(payload.browser.chromium_installed)}</dd>
          <dt>Headless Chromium</dt>
          <dd>{yesNo(payload.browser.chromium_headless_installed)}</dd>
        </dl>
      </section>
    );
  }

  if (kind === 'sessions') {
    return (
      <section className="capability-dialog">
        <h2>会话</h2>
        <table>
          <thead>
            <tr>
              <th>标题</th>
              <th>ID</th>
              <th>模型</th>
              <th>工作区</th>
            </tr>
          </thead>
          <tbody>
            {payload.map(session => (
              <tr key={session.id}>
                <td>{session.title || '网页聊天'}</td>
                <td>{session.id.slice(0, 8)}</td>
                <td>{session.model || '-'}</td>
                <td>{session.workspace_path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  }

  if (kind === 'help') {
    return (
      <section className="capability-dialog">
        <h2>可用命令</h2>
        <table>
          <thead>
            <tr>
              <th>命令</th>
              <th>说明</th>
              <th>用法</th>
            </tr>
          </thead>
          <tbody>
            {payload.map(command => (
              <tr key={command.name}>
                <td>{command.name}</td>
                <td>{command.description}</td>
                <td>{command.usage}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  }

  return (
    <section className="capability-dialog">
      <h2>运行状态</h2>
      <dl>
        <dt>连接</dt>
        <dd>{payload.status}</dd>
        <dt>会话</dt>
        <dd>{payload.activeSessionId || '未选择'}</dd>
        <dt>模型</dt>
        <dd>{payload.model || '默认配置'}</dd>
        <dt>工作区</dt>
        <dd>{payload.workspacePath || '默认配置'}</dd>
      </dl>
    </section>
  );
}

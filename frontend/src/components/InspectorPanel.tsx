import type { SessionRecord } from '../api/types';

type InspectorPanelProps = {
  activeSession: SessionRecord | null;
  loadError?: string | null;
  model?: string | null;
  notice?: string | null;
  status: string;
  workspacePath?: string | null;
};

function valueOrFallback(value: string | null | undefined, fallback: string): string {
  return value && value.trim() ? value : fallback;
}

export function InspectorPanel({
  activeSession,
  loadError,
  model,
  notice,
  status,
  workspacePath,
}: InspectorPanelProps) {
  const signal = loadError || notice || status;

  return (
    <aside className="inspector-panel" aria-label="运行检查器">
      <section className="inspector-card">
        <p className="panel-kicker">Current Run</p>
        <h2>当前任务</h2>
        <dl className="inspector-list">
          <div>
            <dt>Session</dt>
            <dd>{activeSession?.id || '未选择会话'}</dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{valueOrFallback(model, '未设置模型')}</dd>
          </div>
          <div>
            <dt>Workspace</dt>
            <dd>{valueOrFallback(workspacePath, '未设置工作区')}</dd>
          </div>
        </dl>
      </section>
      <section className="inspector-card inspector-signal">
        <p className="panel-kicker">Signal</p>
        <p>{signal}</p>
      </section>
      <section className="inspector-card">
        <p className="panel-kicker">Commands</p>
        <div className="command-chip-list" aria-label="命令提示">
          <span>/status</span>
          <span>/doctor</span>
          <span>/mcp</span>
          <span>/skills</span>
        </div>
      </section>
    </aside>
  );
}

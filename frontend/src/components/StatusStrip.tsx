import type { SessionRecord } from '../api/types';

export type StatusStripProps = {
  activeSession: SessionRecord | null;
  model?: string | null;
  workspacePath?: string | null;
  status: string;
};

function shortSessionId(session: SessionRecord | null): string {
  return session ? session.id.slice(0, 8) : '未选择';
}

function valueOrFallback(value: string | null | undefined, fallback: string): string {
  return value && value.trim() ? value : fallback;
}

export function StatusStrip({ activeSession, model, status, workspacePath }: StatusStripProps) {
  const items = [
    { label: 'Session', value: shortSessionId(activeSession) },
    { label: 'Model', value: valueOrFallback(model, '未设置模型') },
    { label: 'Workspace', value: valueOrFallback(workspacePath, '未设置工作区') },
    { label: 'Link', value: status },
  ];

  return (
    <header className="status-strip" aria-label="运行上下文">
      <div className="status-strip-mark" aria-hidden="true">
        EC
      </div>
      <dl className="status-strip-items">
        {items.map(item => (
          <div className="status-strip-item" key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      <nav className="status-strip-commands" aria-label="常用命令">
        <span>/doctor</span>
        <span>/mcp</span>
        <span>/skills</span>
      </nav>
    </header>
  );
}

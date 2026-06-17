import type { SessionRecord } from '../api/types';

export function Sidebar({
  activeSessionId,
  onNewSession,
  onSelectSession,
  sessions,
  status,
}: {
  activeSessionId: string | null;
  onNewSession: () => void;
  onSelectSession: (sessionId: string) => void;
  sessions: SessionRecord[];
  status: string;
}) {
  return (
    <aside className="sidebar" aria-label="会话列表">
      <div className="sidebar-header">
        <p className="eyebrow">Local Agent</p>
        <h1>Easy Claw</h1>
        <div className="status-pill" aria-label="连接状态">
          {status}
        </div>
      </div>
      <button className="new-session-button" onClick={onNewSession} type="button">
        新建会话
      </button>
      <nav className="session-list" aria-label="历史会话">
        {sessions.length ? (
          sessions.map(session => (
            <button
              aria-current={session.id === activeSessionId ? 'true' : undefined}
              className="session-button"
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              type="button"
            >
              <span>{session.title || '网页聊天'}</span>
              <small>{session.id.slice(0, 8)}</small>
            </button>
          ))
        ) : (
          <p className="empty-note">暂无会话</p>
        )}
      </nav>
    </aside>
  );
}

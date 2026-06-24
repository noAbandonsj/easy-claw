import type { SessionRecord } from '../api/types';

export function Sidebar({
  activeSessionId,
  onDeleteSession,
  onNewSession,
  onSelectSession,
  sessions,
  status,
}: {
  activeSessionId: string | null;
  onDeleteSession: (sessionId: string) => void;
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
          sessions.map(session => {
            const title = session.title || '网页聊天';
            return (
              <div className="session-row" key={session.id}>
                <button
                  aria-current={session.id === activeSessionId ? 'true' : undefined}
                  className="session-button"
                  onClick={() => onSelectSession(session.id)}
                  type="button"
                >
                  <span>{title}</span>
                  <small>{session.id.slice(0, 8)}</small>
                </button>
                <button
                  aria-label={`删除会话 ${title}`}
                  className="delete-session-button"
                  onClick={() => onDeleteSession(session.id)}
                  title="删除会话"
                  type="button"
                >
                  ×
                </button>
              </div>
            );
          })
        ) : (
          <p className="empty-note">暂无会话</p>
        )}
      </nav>
    </aside>
  );
}

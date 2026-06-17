import { useEffect, useState } from 'react';
import { createSession, listSessions } from './api/http';
import type { SessionRecord } from './api/types';
import { AppShell } from './components/AppShell';
import { ChatInput } from './components/ChatInput';
import { ChatView } from './components/ChatView';
import { Sidebar } from './components/Sidebar';
import { useChatSocket } from './hooks/useChatSocket';

export function App() {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const chat = useChatSocket(activeSessionId);

  useEffect(() => {
    let active = true;

    async function loadInitialSession() {
      try {
        const records = await listSessions();
        if (!active) {
          return;
        }
        if (records.length) {
          setSessions(records);
          setActiveSessionId(records[0].id);
          return;
        }
        const created = await createSession();
        if (!active) {
          return;
        }
        setSessions([created]);
        setActiveSessionId(created.id);
      } catch (error) {
        if (active) {
          setLoadError(error instanceof Error ? error.message : '无法加载会话');
        }
      }
    }

    void loadInitialSession();

    return () => {
      active = false;
    };
  }, []);

  async function newSession() {
    const created = await createSession();
    setSessions(current => [created, ...current]);
    setActiveSessionId(created.id);
  }

  return (
    <AppShell
      sidebar={
        <Sidebar
          activeSessionId={activeSessionId}
          onNewSession={() => void newSession()}
          onSelectSession={setActiveSessionId}
          sessions={sessions}
          status={loadError || chat.status}
        />
      }
    >
      <ChatView blocks={chat.blocks} />
      <ChatInput disabled={chat.readyState !== 'open'} onSubmit={chat.sendPrompt} />
    </AppShell>
  );
}

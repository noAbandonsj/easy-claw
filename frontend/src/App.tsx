import { useEffect, useState } from 'react';
import {
  createSession,
  fetchBrowser,
  fetchMcp,
  fetchSkills,
  fetchSlashCommands,
  listSessions,
  resolveSession,
} from './api/http';
import type { SessionRecord } from './api/types';
import { AppShell } from './components/AppShell';
import { CapabilityDialog } from './components/CapabilityDialogs';
import { ChatInput } from './components/ChatInput';
import { ChatView } from './components/ChatView';
import { Modal } from './components/Modal';
import { Sidebar } from './components/Sidebar';
import { useChatSocket } from './hooks/useChatSocket';
import { parseSlashCommand } from './state/slashCommands';

type DialogState = {
  props: Parameters<typeof CapabilityDialog>[0];
};

export function App() {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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

  async function openSessionsDialog() {
    const records = await listSessions();
    setSessions(records);
    setDialog({ props: { kind: 'sessions', payload: records } });
  }

  async function handleSlashCommand(content: string) {
    const command = parseSlashCommand(content);
    if (!command) {
      setNotice(null);
      chat.sendPrompt(content);
      return;
    }

    switch (command.name) {
      case 'skills':
        setDialog({ props: { kind: 'skills', payload: await fetchSkills() } });
        break;
      case 'mcp':
        setDialog({ props: { kind: 'mcp', payload: await fetchMcp() } });
        break;
      case 'browser':
        setDialog({ props: { kind: 'browser', payload: await fetchBrowser() } });
        break;
      case 'sessions':
        await openSessionsDialog();
        break;
      case 'help':
        setDialog({ props: { kind: 'help', payload: await fetchSlashCommands() } });
        break;
      case 'status':
        setDialog({
          props: {
            kind: 'status',
            payload: { activeSessionId, status: loadError || chat.status },
          },
        });
        break;
      case 'resume': {
        if (!command.arg) {
          setNotice('请提供会话 ID。');
          break;
        }
        const session = await resolveSession(command.arg);
        setSessions(current => [session, ...current.filter(item => item.id !== session.id)]);
        setActiveSessionId(session.id);
        setNotice(`已恢复会话 ${session.id.slice(0, 8)}`);
        break;
      }
      case 'clear':
        chat.clearBlocks();
        setNotice(null);
        break;
      case 'save':
        setNotice('网页会话会自动保存。');
        break;
      case 'exit':
        setNotice('网页端无需退出，关闭页面即可。');
        break;
      case 'unsupported':
        setNotice('该命令目前仅支持在终端中使用。');
        break;
      default:
        break;
    }
  }

  return (
    <AppShell
      sidebar={
        <Sidebar
          activeSessionId={activeSessionId}
          onNewSession={() => void newSession()}
          onSelectSession={setActiveSessionId}
          sessions={sessions}
          status={notice || loadError || chat.status}
        />
      }
    >
      <ChatView blocks={chat.blocks} />
      <ChatInput
        disabled={chat.readyState !== 'open'}
        onSubmit={content => void handleSlashCommand(content)}
      />
      {dialog ? (
        <Modal onClose={() => setDialog(null)}>
          <CapabilityDialog {...dialog.props} />
        </Modal>
      ) : null}
    </AppShell>
  );
}

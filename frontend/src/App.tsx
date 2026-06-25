import { useEffect, useState } from 'react';
import {
  createSession,
  deleteSession,
  fetchBrowser,
  fetchDoctor,
  fetchMcp,
  fetchSkills,
  fetchSlashCommands,
  listSessions,
  resolveSession,
  resolveWorkspace,
  saveConversation,
} from './api/http';
import type { MessageBlock, SaveConversationMessage, SessionRecord } from './api/types';
import { AppShell } from './components/AppShell';
import { CapabilityDialog } from './components/CapabilityDialogs';
import { ChatInput } from './components/ChatInput';
import { ChatView } from './components/ChatView';
import { InspectorPanel } from './components/InspectorPanel';
import { Modal } from './components/Modal';
import { Sidebar } from './components/Sidebar';
import { StatusStrip } from './components/StatusStrip';
import { useChatSocket } from './hooks/useChatSocket';
import { parseSlashCommand } from './state/slashCommands';

type DialogState = {
  props: Parameters<typeof CapabilityDialog>[0];
};

type WebConfigOverrides = {
  model?: string | null;
  workspacePath?: string | null;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败';
}

function messagesForSave(blocks: MessageBlock[]): SaveConversationMessage[] {
  return blocks.flatMap(block => {
    if (block.kind === 'user' || block.kind === 'assistant') {
      return [{ kind: block.kind, content: block.content }];
    }
    return [];
  });
}

export function App() {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [webConfig, setWebConfig] = useState<WebConfigOverrides>({});
  const chat = useChatSocket(activeSessionId, webConfig);
  const activeSession = sessions.find(session => session.id === activeSessionId) || null;

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

  function sessionCreateOptions() {
    return {
      model: webConfig.model,
      workspace_path: webConfig.workspacePath,
    };
  }

  async function newSession() {
    const created = await createSession('网页聊天', sessionCreateOptions());
    setSessions(current => [created, ...current]);
    setActiveSessionId(created.id);
  }

  async function deleteSessionById(sessionId: string) {
    const result = await deleteSession(sessionId);
    const deletedId = result.session.id;
    let remaining = sessions.filter(session => session.id !== deletedId);
    setSessions(remaining);
    if (activeSessionId === deletedId) {
      if (remaining.length) {
        setActiveSessionId(remaining[0].id);
      } else {
        const created = await createSession('网页聊天', sessionCreateOptions());
        remaining = [created];
        setSessions(remaining);
        setActiveSessionId(created.id);
      }
    }
    setNotice(`已删除会话 ${deletedId.slice(0, 8)}`);
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

    try {
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
        case 'doctor':
          setDialog({ props: { kind: 'doctor', payload: await fetchDoctor() } });
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
              payload: {
                activeSessionId,
                model: webConfig.model || activeSession?.model,
                status: loadError || chat.status,
                workspacePath: webConfig.workspacePath || activeSession?.workspace_path,
              },
            },
          });
          break;
        case 'workspace': {
          if (!command.arg) {
            setNotice('用法：/workspace <path>');
            break;
          }
          const resolved = await resolveWorkspace(command.arg);
          setWebConfig(current => ({
            ...current,
            workspacePath: resolved.workspace_path,
          }));
          setNotice(`工作区已切换到 ${resolved.workspace_path}`);
          break;
        }
        case 'model':
          if (!command.arg) {
            setNotice('用法：/model <name>');
            break;
          }
          setWebConfig(current => ({ ...current, model: command.arg }));
          setNotice(`模型已切换到 ${command.arg}`);
          break;
        case 'save':
          if (!command.arg) {
            setNotice('用法：/save <path>');
            break;
          }
          if (!activeSessionId) {
            setNotice('请先选择或新建会话。');
            break;
          }
          await saveConversation({
            messages: messagesForSave(chat.blocks),
            model: webConfig.model || activeSession?.model,
            path: command.arg,
            session_id: activeSessionId,
            workspace_path: webConfig.workspacePath || activeSession?.workspace_path,
          });
          setNotice(`对话已保存到 ${command.arg}`);
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
        case 'delete-session':
          if (!command.arg) {
            setNotice('用法：/delete-session <session-id>');
            break;
          }
          await deleteSessionById(command.arg);
          break;
        case 'clear':
          chat.clearBlocks();
          setNotice(null);
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
    } catch (error) {
      setNotice(errorMessage(error));
    }
  }

  return (
    <AppShell
      topbar={
        <StatusStrip
          activeSession={activeSession}
          model={webConfig.model || activeSession?.model}
          status={loadError || chat.status}
          workspacePath={webConfig.workspacePath || activeSession?.workspace_path}
        />
      }
      inspector={
        <InspectorPanel
          activeSession={activeSession}
          loadError={loadError}
          model={webConfig.model || activeSession?.model}
          notice={notice}
          status={loadError || chat.status}
          workspacePath={webConfig.workspacePath || activeSession?.workspace_path}
        />
      }
      sidebar={
        <Sidebar
          activeSessionId={activeSessionId}
          onDeleteSession={sessionId => void deleteSessionById(sessionId)}
          onNewSession={() => void newSession()}
          onSelectSession={setActiveSessionId}
          sessions={sessions}
          status={notice || loadError || chat.status}
        />
      }
    >
      <ChatView blocks={chat.blocks} onApprovalDecision={chat.sendApprovalDecision} />
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

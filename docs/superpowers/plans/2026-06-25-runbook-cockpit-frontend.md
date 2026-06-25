# Runbook Cockpit Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the easy-claw React web UI into a high-density local agent task console with tokenized theming foundations and a Claw Rail execution stream.

**Architecture:** Keep the existing backend, WebSocket protocol, session model, and slash-command behavior. Add small presentational components for top status and inspector metadata, expand the shell layout, then restyle existing chat, tool, approval, modal, and navigation surfaces through semantic CSS tokens.

**Tech Stack:** React, TypeScript, Vite, Vitest, Testing Library, CSS custom properties, existing `MessageBlock` and `SessionRecord` API types.

## Global Constraints

- Use semantic CSS variables rather than hard-coded component colors.
- Default visual identity is `Obsidian Runbook`.
- Do not add theme switching UI.
- Do not persist theme preferences.
- Do not add new backend APIs.
- Do not add new WebSocket message types.
- Do not change the backend session model.
- Do not add dashboard charts.
- Do not add external font or icon dependencies.
- Use `"Segoe UI Variable", "Microsoft YaHei UI", system-ui, sans-serif` for UI text.
- Use `"Cascadia Code", "JetBrains Mono", "Consolas", monospace` for IDs, command names, file paths, tool arguments, code, timing, and compact metadata.
- Respect `prefers-reduced-motion: reduce`.
- Preserve existing aria labels or replace them with equally clear Chinese labels.
- Use PowerShell examples in docs and scripts, but use Bash-compatible commands in this Claude Code environment when running tools.

---

## File Structure

Create:

- `frontend/src/components/StatusStrip.tsx` — presentational top status strip; renders known session/model/workspace/status metadata and command hints; performs no fetching.
- `frontend/src/components/StatusStrip.test.tsx` — unit tests for status strip copy and fallback values.
- `frontend/src/components/InspectorPanel.tsx` — presentational right inspector; renders known session/model/workspace/status plus notices and command hints; performs no fetching.
- `frontend/src/components/InspectorPanel.test.tsx` — unit tests for inspector metadata and notice rendering.

Modify:

- `frontend/src/components/AppShell.tsx` — expand shell contract to accept `topbar`, `sidebar`, and `inspector` regions around the execution area.
- `frontend/src/App.tsx` — compose new `StatusStrip` and `InspectorPanel` from existing state; pass expanded shell props; keep API and WebSocket behavior unchanged.
- `frontend/src/App.test.tsx` — update assertions for the command dock button, runbook shell, and inspector/status metadata.
- `frontend/src/components/Sidebar.tsx` — update copy and markup to runbook nav language while preserving callbacks and accessibility.
- `frontend/src/components/Sidebar.test.tsx` — update copy assertions and verify delete/select behavior remains unchanged.
- `frontend/src/components/ChatInput.tsx` — restyle through class hooks and change button text from `发送` to `执行`; keep Enter submission.
- `frontend/src/components/ChatInput.test.tsx` — update button text and disabled-state assertion.
- `frontend/src/components/ChatView.tsx` — wrap stream in Claw Rail structure and replace empty state with task-console welcome panel.
- `frontend/src/components/MessageBlockView.tsx` — wrap each block in a rail event with kind/status classes and render existing content inside.
- `frontend/src/components/MarkdownMessage.tsx` — allow rail wrapper to own event positioning while keeping assistant message styling.
- `frontend/src/components/ToolCard.tsx` — add run-event semantics and state metadata classes; preserve collapse/copy behavior.
- `frontend/src/components/ToolCard.test.tsx` — verify run-event label, status, collapse, copy, and running-args behavior.
- `frontend/src/components/ApprovalCard.tsx` — restyle as risk gate and add explicit labels for approval status.
- `frontend/src/components/ApprovalCard.test.tsx` — update or add risk gate assertions.
- `frontend/src/styles.css` — replace current visual system with Obsidian Runbook tokens, layout, Claw Rail, component, responsive, focus, and reduced-motion CSS.
- `frontend/src/styles.test.ts` — update CSS contract tests for tokens, viewport containment, rail CSS, responsive CSS, and reduced-motion CSS.

Do not modify:

- `frontend/src/api/types.ts`
- `frontend/src/api/http.ts`
- `frontend/src/api/chatSocket.ts`
- backend Python files

---

### Task 1: Add read-only status and inspector components

**Files:**
- Create: `frontend/src/components/StatusStrip.tsx`
- Create: `frontend/src/components/StatusStrip.test.tsx`
- Create: `frontend/src/components/InspectorPanel.tsx`
- Create: `frontend/src/components/InspectorPanel.test.tsx`

**Interfaces:**
- Consumes: no project-specific components; imports `SessionRecord` type from `../api/types`.
- Produces:
  - `StatusStrip(props: StatusStripProps): JSX.Element`
  - `InspectorPanel(props: InspectorPanelProps): JSX.Element`
  - `StatusStripProps = { activeSession: SessionRecord | null; model?: string | null; workspacePath?: string | null; status: string; }`
  - `InspectorPanelProps = StatusStripProps & { notice?: string | null; loadError?: string | null; }`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/StatusStrip.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusStrip } from './StatusStrip';

const session = {
  id: 'session-1234567890',
  title: '网页聊天',
  workspace_path: 'D:/workspace',
  model: 'deepseek-v4-pro',
  created_at: '2026-06-17T00:00:00+00:00',
  updated_at: '2026-06-17T00:00:00+00:00',
};

describe('StatusStrip', () => {
  it('renders compact run context from known state', () => {
    render(
      <StatusStrip
        activeSession={session}
        model="claude-opus-4-8"
        status="已连接"
        workspacePath="D:/repo"
      />,
    );

    expect(screen.getByLabelText('运行上下文')).toBeInTheDocument();
    expect(screen.getByText('session-')).toBeInTheDocument();
    expect(screen.getByText('claude-opus-4-8')).toBeInTheDocument();
    expect(screen.getByText('D:/repo')).toBeInTheDocument();
    expect(screen.getByText('已连接')).toBeInTheDocument();
    expect(screen.getByText('/doctor')).toBeInTheDocument();
    expect(screen.getByText('/mcp')).toBeInTheDocument();
    expect(screen.getByText('/skills')).toBeInTheDocument();
  });

  it('renders stable fallback values before a session is selected', () => {
    render(<StatusStrip activeSession={null} model={null} status="正在连接" workspacePath={null} />);

    expect(screen.getByText('未选择')).toBeInTheDocument();
    expect(screen.getByText('未设置模型')).toBeInTheDocument();
    expect(screen.getByText('未设置工作区')).toBeInTheDocument();
  });
});
```

Create `frontend/src/components/InspectorPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { InspectorPanel } from './InspectorPanel';

const session = {
  id: 'session-abcdef123456',
  title: '网页聊天',
  workspace_path: 'D:/workspace',
  model: 'deepseek-v4-pro',
  created_at: '2026-06-17T00:00:00+00:00',
  updated_at: '2026-06-17T00:00:00+00:00',
};

describe('InspectorPanel', () => {
  it('renders current run metadata and command hints', () => {
    render(
      <InspectorPanel
        activeSession={session}
        loadError={null}
        model="deepseek-v4-pro"
        notice="模型已切换"
        status="就绪"
        workspacePath="D:/workspace"
      />,
    );

    expect(screen.getByRole('complementary', { name: '运行检查器' })).toBeInTheDocument();
    expect(screen.getByText('当前任务')).toBeInTheDocument();
    expect(screen.getByText('session-abcdef123456')).toBeInTheDocument();
    expect(screen.getByText('deepseek-v4-pro')).toBeInTheDocument();
    expect(screen.getByText('D:/workspace')).toBeInTheDocument();
    expect(screen.getByText('模型已切换')).toBeInTheDocument();
    expect(screen.getByText('/status')).toBeInTheDocument();
  });

  it('prefers load errors over notices in the signal area', () => {
    render(
      <InspectorPanel
        activeSession={null}
        loadError="无法加载会话"
        model={null}
        notice="已保存"
        status="错误"
        workspacePath={null}
      />,
    );

    expect(screen.getByText('无法加载会话')).toBeInTheDocument();
    expect(screen.queryByText('已保存')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --run src/components/StatusStrip.test.tsx src/components/InspectorPanel.test.tsx
```

Expected: FAIL because `StatusStrip.tsx` and `InspectorPanel.tsx` do not exist.

- [ ] **Step 3: Implement `StatusStrip`**

Create `frontend/src/components/StatusStrip.tsx`:

```tsx
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
```

- [ ] **Step 4: Implement `InspectorPanel`**

Create `frontend/src/components/InspectorPanel.tsx`:

```tsx
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run src/components/StatusStrip.test.tsx src/components/InspectorPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/StatusStrip.tsx frontend/src/components/StatusStrip.test.tsx frontend/src/components/InspectorPanel.tsx frontend/src/components/InspectorPanel.test.tsx
git commit -m "feat(frontend): add runbook context panels"
```

---

### Task 2: Expand the application shell and compose cockpit regions

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes from Task 1:
  - `StatusStrip`
  - `InspectorPanel`
- Produces:
  - `AppShell({ children, inspector, sidebar, topbar }: { children: ReactNode; inspector: ReactNode; sidebar: ReactNode; topbar: ReactNode; }): JSX.Element`
  - `App` renders status strip, sidebar, execution pane, inspector, command dock, and modal without changing network calls.

- [ ] **Step 1: Update the failing app test expectations**

Modify `frontend/src/App.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

class MockWebSocket {
  static CLOSED = 3;
  static CONNECTING = 0;
  static OPEN = 1;

  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  readyState = MockWebSocket.CONNECTING;
  url: string;

  static instances: MockWebSocket[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.();
    });
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  send() {}
}

describe('App', () => {
  afterEach(() => {
    MockWebSocket.instances = [];
    vi.unstubAllGlobals();
  });

  it('loads sessions into the runbook cockpit shell', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: 'session-1',
            title: '网页聊天',
            workspace_path: 'D:/workspace',
            model: 'deepseek-v4-pro',
            created_at: '2026-06-17T00:00:00+00:00',
            updated_at: '2026-06-17T00:00:00+00:00',
          },
        ],
      }),
    );

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Easy Claw' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /^网页聊天/ })).toBeInTheDocument();
    expect(screen.getByLabelText('运行上下文')).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: '运行检查器' })).toBeInTheDocument();
    expect(screen.getByText('D:/workspace')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText('消息')).not.toBeDisabled());
  });

  it('opens doctor details from the slash command', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === '/sessions') {
          return {
            ok: true,
            json: async () => [
              {
                id: 'session-1',
                title: '网页聊天',
                workspace_path: 'D:/workspace',
                model: 'deepseek-v4-pro',
                created_at: '2026-06-17T00:00:00+00:00',
                updated_at: '2026-06-17T00:00:00+00:00',
              },
            ],
          };
        }
        if (path === '/doctor') {
          return {
            ok: true,
            json: async () => ({
              api_key_configured: true,
              approval_mode: 'permissive',
              base_url: 'https://api.example.com',
              browser: {
                chromium_headless_installed: false,
                chromium_installed: true,
                enabled: false,
                headless: false,
              },
              checkpoint_db_path: 'D:/repo/data/checkpoints.sqlite',
              data_dir: 'D:/repo/data',
              execution_mode: 'local',
              mcp_config_path: 'mcp_servers.json',
              mcp_mode: 'disabled',
              mcp_status: '已关闭',
              model: 'deepseek-v4-pro',
              product_db_path: 'D:/repo/data/easy-claw.db',
              version: '0.5.0',
              workspace: 'D:/workspace',
            }),
          };
        }
        throw new Error(`unexpected fetch ${path}`);
      }),
    );

    render(<App />);

    const input = await screen.findByLabelText('消息');
    await waitFor(() => expect(input).not.toBeDisabled());
    fireEvent.change(input, { target: { value: '/doctor' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    expect(await screen.findByRole('heading', { name: '本地诊断' })).toBeInTheDocument();
    expect(screen.getByText('deepseek-v4-pro')).toBeInTheDocument();
  });

  it('deletes a session from the sidebar', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === '/sessions' && !init) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'session-1',
              title: '第一会话',
              workspace_path: 'D:/workspace',
              model: 'deepseek-v4-pro',
              created_at: '2026-06-17T00:00:00+00:00',
              updated_at: '2026-06-17T00:00:00+00:00',
            },
            {
              id: 'session-2',
              title: '第二会话',
              workspace_path: 'D:/workspace',
              model: 'deepseek-v4-pro',
              created_at: '2026-06-17T00:00:00+00:00',
              updated_at: '2026-06-17T00:00:00+00:00',
            },
          ],
        };
      }
      if (path === '/sessions/session-1' && init?.method === 'DELETE') {
        return {
          ok: true,
          json: async () => ({ deleted: true, session: { id: 'session-1' } }),
        };
      }
      throw new Error(`unexpected fetch ${path}`);
    });
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);

    expect(await screen.findByRole('button', { name: /^第一会话/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '删除会话 第一会话' }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/sessions/session-1', { method: 'DELETE' }),
    );
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /^第一会话/ })).not.toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^第二会话/ })).toHaveAttribute(
        'aria-current',
        'true',
      ),
    );
  });
});
```

- [ ] **Step 2: Run the app tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --run src/App.test.tsx
```

Expected: FAIL because `AppShell` has not accepted `topbar`/`inspector`, and `App` does not render the new regions.

- [ ] **Step 3: Expand `AppShell`**

Replace `frontend/src/components/AppShell.tsx` with:

```tsx
import type { ReactNode } from 'react';

export function AppShell({
  children,
  inspector,
  sidebar,
  topbar,
}: {
  children: ReactNode;
  inspector: ReactNode;
  sidebar: ReactNode;
  topbar: ReactNode;
}) {
  return (
    <main className="app-shell">
      {topbar}
      <div className="workbench-grid">
        {sidebar}
        <section className="chat-pane" aria-label="任务执行区">
          {children}
        </section>
        {inspector}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Compose new regions in `App`**

Modify imports in `frontend/src/App.tsx`:

```tsx
import { InspectorPanel } from './components/InspectorPanel';
import { StatusStrip } from './components/StatusStrip';
```

Replace the return block in `frontend/src/App.tsx` with:

```tsx
  const effectiveModel = webConfig.model || activeSession?.model;
  const effectiveWorkspace = webConfig.workspacePath || activeSession?.workspace_path;
  const effectiveStatus = notice || loadError || chat.status;

  return (
    <AppShell
      topbar={
        <StatusStrip
          activeSession={activeSession}
          model={effectiveModel}
          status={effectiveStatus}
          workspacePath={effectiveWorkspace}
        />
      }
      sidebar={
        <Sidebar
          activeSessionId={activeSessionId}
          onDeleteSession={sessionId => void deleteSessionById(sessionId)}
          onNewSession={() => void newSession()}
          onSelectSession={setActiveSessionId}
          sessions={sessions}
          status={effectiveStatus}
        />
      }
      inspector={
        <InspectorPanel
          activeSession={activeSession}
          loadError={loadError}
          model={effectiveModel}
          notice={notice}
          status={chat.status}
          workspacePath={effectiveWorkspace}
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
```

Place the three `const effective...` lines immediately before `return`. Remove the old inline `webConfig.model || activeSession?.model` and `webConfig.workspacePath || activeSession?.workspace_path` duplication only inside the return block.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run src/components/StatusStrip.test.tsx src/components/InspectorPanel.test.tsx src/App.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit the shell composition**

```bash
git add frontend/src/components/AppShell.tsx frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): compose runbook cockpit shell"
```

If TypeScript reports a syntax error or a prop mismatch, fix it before committing.

---

### Task 3: Convert the sidebar into Runbook Nav

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/Sidebar.test.tsx`

**Interfaces:**
- Consumes: existing `SessionRecord` type and callback props.
- Produces: same `Sidebar` function signature as before; visual/copy-only behavior changes.

- [ ] **Step 1: Write the failing sidebar tests**

Replace `frontend/src/components/Sidebar.test.tsx` with:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Sidebar } from './Sidebar';

const session = {
  id: 'session-1',
  title: '网页聊天',
  workspace_path: 'D:/workspace',
  model: 'deepseek-v4-pro',
  created_at: '2026-06-17T00:00:00+00:00',
  updated_at: '2026-06-17T00:00:00+00:00',
};

describe('Sidebar', () => {
  it('renders runbook navigation and the active task record', () => {
    render(
      <Sidebar
        activeSessionId="session-1"
        onDeleteSession={vi.fn()}
        onNewSession={vi.fn()}
        onSelectSession={vi.fn()}
        sessions={[session]}
        status="就绪"
      />,
    );

    expect(screen.getByRole('heading', { name: 'Easy Claw' })).toBeInTheDocument();
    expect(screen.getByText('Local Agent Runbook')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '新建任务' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^网页聊天/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
    expect(screen.getByText('session-')).toBeInTheDocument();
    expect(screen.getByLabelText('连接状态')).toHaveTextContent('就绪');
  });

  it('calls delete handler without selecting the session', () => {
    const onDeleteSession = vi.fn();
    const onSelectSession = vi.fn();
    render(
      <Sidebar
        activeSessionId="session-1"
        onDeleteSession={onDeleteSession}
        onNewSession={vi.fn()}
        onSelectSession={onSelectSession}
        sessions={[session]}
        status="就绪"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '删除会话 网页聊天' }));

    expect(onDeleteSession).toHaveBeenCalledWith('session-1');
    expect(onSelectSession).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run sidebar tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --run src/components/Sidebar.test.tsx
```

Expected: FAIL because copy still says `Local Agent` and `新建会话`.

- [ ] **Step 3: Update `Sidebar` markup and copy**

Replace `frontend/src/components/Sidebar.tsx` with:

```tsx
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
    <aside className="sidebar" aria-label="任务记录">
      <div className="sidebar-header">
        <p className="eyebrow">Local Agent Runbook</p>
        <h1>Easy Claw</h1>
        <div className="status-pill" aria-label="连接状态">
          <span className="status-dot" aria-hidden="true" />
          {status}
        </div>
      </div>
      <button className="new-session-button" onClick={onNewSession} type="button">
        新建任务
      </button>
      <nav className="session-list" aria-label="历史任务">
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
          <p className="empty-note">暂无任务记录</p>
        )}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 4: Run sidebar tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run src/components/Sidebar.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Sidebar.tsx frontend/src/components/Sidebar.test.tsx
git commit -m "feat(frontend): turn sidebar into runbook nav"
```

---

### Task 4: Convert ChatInput into the Command Dock

**Files:**
- Modify: `frontend/src/components/ChatInput.tsx`
- Modify: `frontend/src/components/ChatInput.test.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: existing `ChatInput` props `{ disabled: boolean; onSubmit: (content: string) => void; }`.
- Produces: same `ChatInput` signature; submit button text is `执行`; input hint is task-oriented.

- [ ] **Step 1: Write failing ChatInput tests**

Replace `frontend/src/components/ChatInput.test.tsx` with:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatInput } from './ChatInput';

describe('ChatInput', () => {
  it('submits non-empty tasks and clears the field', () => {
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('消息'), { target: { value: '总结 README' } });
    fireEvent.click(screen.getByRole('button', { name: '执行' }));

    expect(onSubmit).toHaveBeenCalledWith('总结 README');
    expect(screen.getByLabelText('消息')).toHaveValue('');
  });

  it('submits with Enter and clears the field', () => {
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('消息'), { target: { value: '/status' } });
    fireEvent.keyDown(screen.getByLabelText('消息'), { key: 'Enter' });

    expect(onSubmit).toHaveBeenCalledWith('/status');
    expect(screen.getByLabelText('消息')).toHaveValue('');
  });

  it('shows a command dock hint and disables execution while unavailable', () => {
    render(<ChatInput disabled={true} onSubmit={vi.fn()} />);

    expect(screen.getByText('自然语言任务或 slash command')).toBeInTheDocument();
    expect(screen.getByText('/doctor')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '执行' })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run ChatInput and App tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --run src/components/ChatInput.test.tsx src/App.test.tsx
```

Expected: FAIL because `ChatInput` still renders `发送` and no command dock hints.

- [ ] **Step 3: Implement command dock markup**

Replace `frontend/src/components/ChatInput.tsx` with:

```tsx
import { FormEvent, KeyboardEvent, useState } from 'react';

export function ChatInput({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (content: string) => void;
}) {
  const [value, setValue] = useState('');

  function submitValue() {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    onSubmit(trimmed);
    setValue('');
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitValue();
  }

  function submitOnEnter(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      submitValue();
    }
  }

  return (
    <form className="composer command-dock" onSubmit={submit}>
      <div className="command-dock-meta">
        <span>自然语言任务或 slash command</span>
        <span>/doctor</span>
        <span>/mcp</span>
        <span>/skills</span>
      </div>
      <div className="command-dock-row">
        <input
          aria-label="消息"
          disabled={disabled}
          onChange={event => setValue(event.target.value)}
          onKeyDown={submitOnEnter}
          placeholder="描述任务，或输入 /doctor、/mcp、/skills"
          value={value}
        />
        <button disabled={disabled || !value.trim()} type="submit">
          执行
        </button>
      </div>
    </form>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run src/components/ChatInput.test.tsx src/App.test.tsx
```

Expected: PASS for ChatInput. App tests should pass if Task 2 shell composition is complete.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatInput.tsx frontend/src/components/ChatInput.test.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): add command dock input"
```

---

### Task 5: Build the Claw Rail execution stream

**Files:**
- Modify: `frontend/src/components/ChatView.tsx`
- Modify: `frontend/src/components/MessageBlockView.tsx`
- Modify: `frontend/src/components/MarkdownMessage.tsx`
- Create or modify tests in: `frontend/src/components/ChatView.test.tsx` if the file exists; otherwise add assertions through `frontend/src/App.test.tsx` only if no dedicated ChatView test exists.

**Interfaces:**
- Consumes: `MessageBlock` union from `../api/types`.
- Produces:
  - `ChatView` renders `<section className="chat-stream claw-rail" aria-label="任务执行轨迹">`.
  - `MessageBlockView` wraps each block in `<div className="rail-event rail-event-${kind}">`.
  - `MarkdownMessage` continues to render assistant markdown as `<article className="message assistant-message markdown-body">`.

- [ ] **Step 1: Add a dedicated ChatView test if it does not exist**

Create `frontend/src/components/ChatView.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ChatView } from './ChatView';

describe('ChatView', () => {
  it('renders an empty task-console welcome panel on the Claw Rail', () => {
    render(<ChatView blocks={[]} />);

    expect(screen.getByLabelText('任务执行轨迹')).toHaveClass('claw-rail');
    expect(screen.getByText('给本地 agent 一个目标')).toBeInTheDocument();
    expect(screen.getByText('总结 README.md')).toBeInTheDocument();
    expect(screen.getByText('运行测试并解释失败')).toBeInTheDocument();
  });

  it('wraps user, assistant, tool, and error blocks as rail events', () => {
    render(
      <ChatView
        blocks={[
          { id: 'user-1', kind: 'user', content: '检查项目' },
          { id: 'assistant-1', kind: 'assistant', content: '我来检查。', streaming: false },
          {
            id: 'tool-1',
            kind: 'tool',
            name: 'read_file',
            args: { path: 'README.md' },
            result: '# easy-claw',
            status: 'finished',
          },
          { id: 'error-1', kind: 'error', content: '执行失败' },
        ]}
      />,
    );

    expect(screen.getByText('检查项目').closest('.rail-event')).toHaveClass('rail-event-user');
    expect(screen.getByText('Easy Claw').closest('.rail-event')).toHaveClass('rail-event-assistant');
    expect(screen.getByRole('heading', { name: 'read_file' }).closest('.rail-event')).toHaveClass(
      'rail-event-tool',
    );
    expect(screen.getByText('执行失败').closest('.rail-event')).toHaveClass('rail-event-error');
  });
});
```

- [ ] **Step 2: Run the ChatView test to verify it fails**

Run:

```bash
cd frontend && npm test -- --run src/components/ChatView.test.tsx
```

Expected: FAIL because the label, `claw-rail`, empty copy, and rail wrappers do not exist.

- [ ] **Step 3: Update `ChatView`**

Replace `frontend/src/components/ChatView.tsx` with:

```tsx
import type { MessageBlock } from '../api/types';
import { MessageBlockView } from './MessageBlockView';

export function ChatView({
  blocks,
  onApprovalDecision,
}: {
  blocks: MessageBlock[];
  onApprovalDecision?: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  return (
    <section className="chat-stream claw-rail" aria-label="任务执行轨迹">
      {blocks.length ? (
        blocks.map(block => (
          <MessageBlockView
            block={block}
            key={block.id}
            onApprovalDecision={onApprovalDecision}
          />
        ))
      ) : (
        <article className="message assistant-message empty-runbook-panel">
          <span className="message-label">Runbook Ready</span>
          <h2>给本地 agent 一个目标</h2>
          <p>描述你要完成的任务，Easy Claw 会把对话、工具调用、审批和结果串成一条执行轨迹。</p>
          <ul className="starter-list">
            <li>总结 README.md</li>
            <li>检查项目结构</li>
            <li>运行测试并解释失败</li>
            <li>读取文件并提炼行动项</li>
          </ul>
        </article>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Update `MessageBlockView` with rail wrappers**

Replace `frontend/src/components/MessageBlockView.tsx` with:

```tsx
import type { MessageBlock } from '../api/types';
import { ApprovalCard } from './ApprovalCard';
import { MarkdownMessage } from './MarkdownMessage';
import { ToolCard } from './ToolCard';

function railClass(block: MessageBlock): string {
  const status = 'status' in block ? ` rail-event-${block.status}` : '';
  return `rail-event rail-event-${block.kind}${status}`;
}

export function MessageBlockView({
  block,
  onApprovalDecision,
}: {
  block: MessageBlock;
  onApprovalDecision?: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  let content;

  if (block.kind === 'user') {
    content = (
      <article className="message user-message">
        <span className="message-label">你</span>
        <p>{block.content}</p>
      </article>
    );
  } else if (block.kind === 'assistant') {
    content = <MarkdownMessage content={block.content} streaming={block.streaming} />;
  } else if (block.kind === 'tool') {
    content = <ToolCard block={block} />;
  } else if (block.kind === 'approval') {
    content = (
      <ApprovalCard block={block} onDecision={onApprovalDecision || (() => undefined)} />
    );
  } else {
    content = (
      <article className="message error-message">
        <span className="message-label">错误</span>
        <p>{block.content}</p>
      </article>
    );
  }

  return <div className={railClass(block)}>{content}</div>;
}
```

- [ ] **Step 5: Keep `MarkdownMessage` class contract stable**

Open `frontend/src/components/MarkdownMessage.tsx`. If it already matches this content, leave it unchanged. If it differs, replace it with:

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';

export function MarkdownMessage({
  content,
  streaming,
}: {
  content: string;
  streaming: boolean;
}) {
  return (
    <article className="message assistant-message markdown-body">
      <span className="message-label">Easy Claw</span>
      <ReactMarkdown
        components={{
          a({ children, href }) {
            return (
              <a href={href} rel="noreferrer" target="_blank">
                {children}
              </a>
            );
          },
          code({ children, className }) {
            const value = String(children).replace(/\n$/, '');
            const match = /language-(\w+)/.exec(className || '');
            if (match) {
              return <CodeBlock language={match[1]} value={value} />;
            }
            return <code className={className}>{children}</code>;
          },
        }}
        remarkPlugins={[remarkGfm]}
      >
        {content}
      </ReactMarkdown>
      {streaming ? <span className="cursor" /> : null}
    </article>
  );
}
```

- [ ] **Step 6: Run ChatView tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run src/components/ChatView.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ChatView.tsx frontend/src/components/MessageBlockView.tsx frontend/src/components/MarkdownMessage.tsx frontend/src/components/ChatView.test.tsx
git commit -m "feat(frontend): add claw rail execution stream"
```

---

### Task 6: Restyle tool and approval cards as run events

**Files:**
- Modify: `frontend/src/components/ToolCard.tsx`
- Modify: `frontend/src/components/ToolCard.test.tsx`
- Modify: `frontend/src/components/ApprovalCard.tsx`
- Modify: `frontend/src/components/ApprovalCard.test.tsx`

**Interfaces:**
- Consumes: existing `MessageBlock` tool and approval variants.
- Produces:
  - Tool cards with `run-event-card` class and run-event metadata labels.
  - Approval cards with `risk-gate` class and explicit status text.
  - Existing expand/collapse/copy and approval callback behavior remain unchanged.

- [ ] **Step 1: Update ToolCard tests**

Replace `frontend/src/components/ToolCard.test.tsx` with:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ToolCard } from './ToolCard';

describe('ToolCard', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders a run event card for a merged tool call and result', () => {
    render(
      <ToolCard
        block={{
          id: 'tool-1',
          kind: 'tool',
          name: 'read_file',
          args: { path: 'README.md' },
          result: '# easy-claw',
          status: 'finished',
        }}
      />,
    );

    expect(screen.getByRole('article', { name: '工具调用 read_file' })).toHaveClass(
      'run-event-card',
    );
    expect(screen.getByRole('heading', { name: 'read_file' })).toBeInTheDocument();
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.getByText(/README.md/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开结果' })).toBeInTheDocument();
    expect(screen.queryByText(/easy-claw/)).not.toBeInTheDocument();
  });

  it('copies the tool result', () => {
    const writeText = vi.fn();
    vi.stubGlobal('navigator', { clipboard: { writeText } });

    render(
      <ToolCard
        block={{
          id: 'tool-1',
          kind: 'tool',
          name: 'run_command',
          args: { command: 'uv run pytest' },
          result: '185 passed',
          status: 'finished',
        }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '复制结果' }));

    expect(writeText).toHaveBeenCalledWith('185 passed');
  });

  it('keeps long tool results collapsed until the user expands them', () => {
    const longResult = `${'README content '.repeat(60)}UNIQUE_RESULT_TAIL`;

    render(
      <ToolCard
        block={{
          id: 'tool-1',
          kind: 'tool',
          name: 'read_file',
          args: { path: 'README.md' },
          result: longResult,
          status: 'finished',
        }}
      />,
    );

    expect(screen.getByText(/README.md/)).toBeInTheDocument();
    expect(screen.queryByText(/UNIQUE_RESULT_TAIL/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '展开结果' }));

    expect(screen.getByText(/UNIQUE_RESULT_TAIL/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '收起结果' })).toBeInTheDocument();
  });

  it('does not render empty running arguments as an empty object', () => {
    render(
      <ToolCard
        block={{
          id: 'tool-1',
          kind: 'tool',
          name: 'read_file',
          args: {},
          result: undefined,
          status: 'running',
        }}
      />,
    );

    expect(screen.getByText('正在解析参数...')).toBeInTheDocument();
    expect(screen.queryByText('{}')).not.toBeInTheDocument();
  });

  it('shows a concise argument summary and elapsed duration', () => {
    render(
      <ToolCard
        block={{
          id: 'tool-1',
          kind: 'tool',
          name: 'read_file',
          args: { path: 'README.md' },
          result: '# easy-claw',
          status: 'finished',
          startedAt: 1000,
          finishedAt: 2450,
        }}
      />,
    );

    expect(screen.getByText('README.md')).toBeInTheDocument();
    expect(screen.getByText('1.5s')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Update ApprovalCard tests**

Replace `frontend/src/components/ApprovalCard.test.tsx` with:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApprovalCard } from './ApprovalCard';

const block = {
  id: 'approval-1',
  kind: 'approval' as const,
  approvalId: 'approval-1',
  actions: [{ name: 'run_command', args: { command: 'Remove-Item file.txt' } }],
  status: 'pending' as const,
};

describe('ApprovalCard', () => {
  it('renders a risk gate with action details', () => {
    render(<ApprovalCard block={block} onDecision={vi.fn()} />);

    expect(screen.getByRole('article', { name: '风险审批 run_command' })).toHaveClass('risk-gate');
    expect(screen.getByRole('heading', { name: '风险操作需要确认' })).toBeInTheDocument();
    expect(screen.getByText('待确认')).toBeInTheDocument();
    expect(screen.getByText('run_command')).toBeInTheDocument();
    expect(screen.getByText(/Remove-Item file.txt/)).toBeInTheDocument();
  });

  it('sends approve and reject decisions while pending', () => {
    const onDecision = vi.fn();
    render(<ApprovalCard block={block} onDecision={onDecision} />);

    fireEvent.click(screen.getByRole('button', { name: '批准执行' }));
    fireEvent.click(screen.getByRole('button', { name: '拒绝执行' }));

    expect(onDecision).toHaveBeenNthCalledWith(1, 'approval-1', 'approve');
    expect(onDecision).toHaveBeenNthCalledWith(2, 'approval-1', 'reject');
  });

  it('disables decisions after the approval is resolved', () => {
    render(<ApprovalCard block={{ ...block, status: 'approved' }} onDecision={vi.fn()} />);

    expect(screen.getByText('已批准')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '批准执行' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '拒绝执行' })).toBeDisabled();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --run src/components/ToolCard.test.tsx src/components/ApprovalCard.test.tsx
```

Expected: FAIL because card aria labels, `run-event-card`, `risk-gate`, and new approval copy do not exist.

- [ ] **Step 4: Update `ToolCard`**

Replace the returned JSX in `frontend/src/components/ToolCard.tsx` with this block, keeping helper functions and state declarations unchanged:

```tsx
  return (
    <article
      aria-label={`工具调用 ${block.name}`}
      className={`tool-panel run-event-card ${block.status}`}
    >
      <div className="tool-summary">
        <div>
          <span className="message-label">Run Event</span>
          <h2>{block.name}</h2>
        </div>
        <div className="tool-meta">
          {duration ? <span>{duration}</span> : null}
          <span>{block.status === 'running' ? '执行中' : '已完成'}</span>
        </div>
      </div>
      <div className="tool-section">
        <div className="tool-section-header">
          <strong>参数</strong>
          {hasArgsDetails ? (
            <button onClick={() => setArgsOpen(current => !current)} type="button">
              {argsOpen ? '收起参数' : '查看参数'}
            </button>
          ) : null}
        </div>
        <p className="tool-argument-summary">{argSummary}</p>
        {argsOpen ? <pre>{args}</pre> : null}
      </div>
      {result ? (
        <div className="tool-section">
          <div className="tool-section-header">
            <strong>结果 {formatSize(result)}</strong>
            <div className="tool-actions">
              <button onClick={() => setResultOpen(current => !current)} type="button">
                {resultOpen ? '收起结果' : '展开结果'}
              </button>
              <button onClick={copyResult} type="button">
                复制结果
              </button>
            </div>
          </div>
          {resultOpen ? <pre>{result}</pre> : null}
        </div>
      ) : null}
    </article>
  );
```

The top of `ToolCard.tsx` remains:

```tsx
import type { MessageBlock } from '../api/types';
import { useState } from 'react';
```

- [ ] **Step 5: Update `ApprovalCard`**

Replace `frontend/src/components/ApprovalCard.tsx` with:

```tsx
import type { MessageBlock } from '../api/types';

type ApprovalBlock = Extract<MessageBlock, { kind: 'approval' }>;

function approvalStatusText(status: ApprovalBlock['status']): string {
  if (status === 'approved') {
    return '已批准';
  }
  if (status === 'rejected') {
    return '已拒绝';
  }
  return '待确认';
}

export function ApprovalCard({
  block,
  onDecision,
}: {
  block: ApprovalBlock;
  onDecision: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  const disabled = block.status !== 'pending';
  const primaryAction = block.actions[0]?.name || '未知操作';

  return (
    <article aria-label={`风险审批 ${primaryAction}`} className={`approval-card risk-gate ${block.status}`}>
      <div className="risk-gate-header">
        <div>
          <span className="message-label">Risk Gate</span>
          <h2>风险操作需要确认</h2>
        </div>
        <span className="risk-gate-status">{approvalStatusText(block.status)}</span>
      </div>
      {block.actions.map((action, index) => (
        <div className="approval-action" key={`${action.name}-${index}`}>
          <strong>{action.name}</strong>
          <pre>{JSON.stringify(action.args || {}, null, 2)}</pre>
        </div>
      ))}
      <div className="approval-actions">
        <button
          disabled={disabled}
          onClick={() => onDecision(block.approvalId, 'approve')}
          type="button"
        >
          批准执行
        </button>
        <button
          disabled={disabled}
          onClick={() => onDecision(block.approvalId, 'reject')}
          type="button"
        >
          拒绝执行
        </button>
      </div>
    </article>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run src/components/ToolCard.test.tsx src/components/ApprovalCard.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ToolCard.tsx frontend/src/components/ToolCard.test.tsx frontend/src/components/ApprovalCard.tsx frontend/src/components/ApprovalCard.test.tsx
git commit -m "feat(frontend): style tool and approval events"
```

---

### Task 7: Replace CSS with Obsidian Runbook tokens and responsive cockpit layout

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/styles.test.ts`

**Interfaces:**
- Consumes: class names produced by Tasks 1-6.
- Produces: tokenized CSS contract for `Obsidian Runbook`, viewport-safe shell layout, Claw Rail visuals, focus styles, responsive layout, and reduced-motion handling.

- [ ] **Step 1: Replace style contract tests**

Replace `frontend/src/styles.test.ts` with:

```tsx
/// <reference types="node" />

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(resolve(process.cwd(), 'src', 'styles.css'), 'utf-8');

function declarationsFor(selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = styles.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`));
  const body = match?.[1] ?? '';

  return Object.fromEntries(
    body
      .split(';')
      .map(declaration => declaration.trim())
      .filter(Boolean)
      .map(declaration => {
        const [property, ...valueParts] = declaration.split(':');
        return [property.trim(), valueParts.join(':').trim()];
      }),
  );
}

describe('styles', () => {
  it('defines the Obsidian Runbook theme tokens', () => {
    expect(declarationsFor(':root')).toMatchObject({
      '--color-bg': '#080b0f',
      '--color-panel': '#10161d',
      '--color-panel-raised': '#151d26',
      '--color-line': '#263442',
      '--color-text': '#e6edf3',
      '--color-muted': '#8493a3',
      '--color-agent': '#7dd3fc',
      '--color-user': '#facc15',
      '--color-risk': '#fb7185',
      '--color-ok': '#34d399',
      '--color-warn': '#f59e0b',
      '--color-command': '#a78bfa',
      '--font-ui': '"Segoe UI Variable", "Microsoft YaHei UI", system-ui, sans-serif',
      '--font-mono': '"Cascadia Code", "JetBrains Mono", "Consolas", monospace',
    });
  });

  it('keeps the cockpit shell inside the viewport', () => {
    expect(declarationsFor('.app-shell')).toMatchObject({
      height: '100vh',
      overflow: 'hidden',
    });
    expect(declarationsFor('.workbench-grid')).toMatchObject({
      'min-height': '0',
      overflow: 'hidden',
    });
    expect(declarationsFor('.sidebar')).toMatchObject({
      'min-height': '0',
      overflow: 'hidden',
    });
    expect(declarationsFor('.chat-pane')).toMatchObject({
      'min-height': '0',
      overflow: 'hidden',
    });
  });

  it('contains Claw Rail, responsive, and reduced-motion rules', () => {
    expect(styles).toContain('.claw-rail');
    expect(styles).toContain('.rail-event::before');
    expect(styles).toContain('@media (max-width: 1120px)');
    expect(styles).toContain('@media (max-width: 720px)');
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)');
  });
});
```

- [ ] **Step 2: Run style tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --run src/styles.test.ts
```

Expected: FAIL because the current CSS does not define the required tokens or new layout selectors.

- [ ] **Step 3: Replace `styles.css` with tokenized cockpit CSS**

Replace `frontend/src/styles.css` with:

```css
:root {
  color-scheme: dark;
  --color-bg: #080b0f;
  --color-panel: #10161d;
  --color-panel-raised: #151d26;
  --color-line: #263442;
  --color-text: #e6edf3;
  --color-muted: #8493a3;
  --color-agent: #7dd3fc;
  --color-user: #facc15;
  --color-risk: #fb7185;
  --color-ok: #34d399;
  --color-warn: #f59e0b;
  --color-command: #a78bfa;
  --color-bg-rgb: 8, 11, 15;
  --color-panel-rgb: 16, 22, 29;
  --color-agent-rgb: 125, 211, 252;
  --color-user-rgb: 250, 204, 21;
  --color-risk-rgb: 251, 113, 133;
  --color-command-rgb: 167, 139, 250;
  --font-ui: "Segoe UI Variable", "Microsoft YaHei UI", system-ui, sans-serif;
  --font-mono: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 18px;
  --shadow-panel: 0 24px 80px rgba(0, 0, 0, 0.34);
  font-family: var(--font-ui);
  background: var(--color-bg);
  color: var(--color-text);
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background:
    radial-gradient(circle at 14% 12%, rgba(var(--color-command-rgb), 0.16), transparent 30%),
    radial-gradient(circle at 82% 8%, rgba(var(--color-agent-rgb), 0.14), transparent 28%),
    linear-gradient(135deg, #080b0f 0%, #0d1117 52%, #090d12 100%);
}

button,
input {
  font: inherit;
}

button:focus-visible,
input:focus-visible,
a:focus-visible {
  outline: 2px solid var(--color-user);
  outline-offset: 3px;
}

button {
  cursor: pointer;
}

button:disabled,
input:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.app-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
  background:
    linear-gradient(90deg, rgba(var(--color-agent-rgb), 0.08), transparent 36%),
    rgba(var(--color-bg-rgb), 0.96);
}

.status-strip {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  min-height: 50px;
  padding: 8px 18px;
  border-bottom: 1px solid var(--color-line);
  background: rgba(var(--color-panel-rgb), 0.92);
  backdrop-filter: blur(16px);
}

.status-strip-mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(var(--color-agent-rgb), 0.55);
  border-radius: var(--radius-sm);
  color: var(--color-agent);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  background: rgba(var(--color-agent-rgb), 0.1);
}

.status-strip-items {
  display: flex;
  gap: 18px;
  min-width: 0;
  margin: 0;
  overflow: hidden;
}

.status-strip-item {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.status-strip-item dt,
.panel-kicker,
.eyebrow,
.message-label {
  margin: 0;
  color: var(--color-muted);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.status-strip-item dd {
  margin: 0;
  min-width: 0;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 0.76rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-strip-commands,
.command-chip-list,
.command-dock-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.status-strip-commands span,
.command-chip-list span,
.command-dock-meta span {
  border: 1px solid rgba(var(--color-command-rgb), 0.34);
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--color-command);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  background: rgba(var(--color-command-rgb), 0.08);
}

.workbench-grid {
  display: grid;
  grid-template-columns: minmax(230px, 290px) minmax(0, 1fr) minmax(240px, 300px);
  gap: 16px;
  min-height: 0;
  overflow: hidden;
  padding: 16px;
}

.sidebar,
.chat-pane,
.inspector-panel {
  min-height: 0;
  border: 1px solid rgba(38, 52, 66, 0.9);
  border-radius: var(--radius-lg);
  background: rgba(var(--color-panel-rgb), 0.82);
  box-shadow: var(--shadow-panel);
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
  padding: 18px;
}

.sidebar-header {
  display: grid;
  gap: 10px;
}

h1 {
  margin: 0;
  color: var(--color-text);
  font-size: 1.65rem;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.status-pill {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  width: fit-content;
  min-height: 30px;
  padding: 6px 10px;
  border: 1px solid rgba(var(--color-agent-rgb), 0.38);
  border-radius: 999px;
  color: var(--color-agent);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  background: rgba(var(--color-agent-rgb), 0.08);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-ok);
  box-shadow: 0 0 18px rgba(52, 211, 153, 0.75);
}

.new-session-button,
.session-button,
.delete-session-button,
.composer button,
.tool-section button,
.code-block button,
.approval-actions button,
.modal-close {
  border: 1px solid rgba(var(--color-agent-rgb), 0.36);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: rgba(var(--color-agent-rgb), 0.08);
}

.new-session-button {
  min-height: 42px;
  color: #071015;
  font-weight: 800;
  background: linear-gradient(135deg, var(--color-user), #fde68a);
  border-color: rgba(var(--color-user-rgb), 0.7);
}

.session-list {
  display: grid;
  gap: 8px;
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.session-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 34px;
  gap: 7px;
  align-items: stretch;
}

.session-button {
  display: grid;
  gap: 5px;
  width: 100%;
  min-height: 56px;
  padding: 10px;
  text-align: left;
  background: rgba(230, 237, 243, 0.045);
}

.session-button span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-button small,
.empty-note,
.inspector-list dd,
.tool-meta,
.tool-argument-summary {
  color: var(--color-muted);
  font-family: var(--font-mono);
}

.session-button[aria-current="true"] {
  border-color: rgba(var(--color-user-rgb), 0.75);
  background: rgba(var(--color-user-rgb), 0.1);
}

.delete-session-button {
  width: 34px;
  min-height: 56px;
  padding: 0;
  color: var(--color-muted);
  background: transparent;
}

.delete-session-button:hover,
.delete-session-button:focus-visible {
  border-color: rgba(var(--color-risk-rgb), 0.7);
  color: var(--color-risk);
  background: rgba(var(--color-risk-rgb), 0.1);
}

.chat-pane {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 14px;
  overflow: hidden;
  padding: 18px;
}

.chat-stream {
  min-height: 0;
  overflow: auto;
  padding: 4px 10px 4px 4px;
}

.claw-rail {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.claw-rail::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 15px;
  width: 2px;
  background: linear-gradient(var(--color-user), var(--color-agent), var(--color-command));
  opacity: 0.45;
}

.rail-event {
  position: relative;
  padding-left: 42px;
}

.rail-event::before {
  content: "";
  position: absolute;
  z-index: 1;
  top: 18px;
  left: 7px;
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-panel);
  border-radius: 5px;
  background: var(--color-agent);
  box-shadow: 0 0 22px rgba(var(--color-agent-rgb), 0.55);
}

.rail-event-user::before {
  border-radius: 50%;
  background: var(--color-user);
  box-shadow: 0 0 22px rgba(var(--color-user-rgb), 0.5);
}

.rail-event-tool::before {
  background: var(--color-command);
  box-shadow: 0 0 22px rgba(var(--color-command-rgb), 0.55);
}

.rail-event-approval::before,
.rail-event-error::before {
  background: var(--color-risk);
  box-shadow: 0 0 22px rgba(var(--color-risk-rgb), 0.55);
}

.rail-event-running::before {
  animation: rail-pulse 1.4s ease-in-out infinite;
}

@keyframes rail-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.18);
  }
}

.message,
.tool-panel,
.approval-card {
  max-width: min(840px, 100%);
  padding: 18px;
  border: 1px solid rgba(38, 52, 66, 0.95);
  border-radius: var(--radius-md);
  background: rgba(21, 29, 38, 0.92);
}

.user-message {
  border-color: rgba(var(--color-user-rgb), 0.42);
  background: rgba(var(--color-user-rgb), 0.08);
}

.assistant-message,
.error-message {
  border-color: rgba(var(--color-agent-rgb), 0.24);
}

.error-message,
.risk-gate {
  border-color: rgba(var(--color-risk-rgb), 0.55);
  background: rgba(var(--color-risk-rgb), 0.08);
}

.message h2,
.approval-card h2,
.tool-summary h2,
.inspector-card h2 {
  margin: 4px 0 0;
  color: var(--color-text);
  line-height: 1.2;
}

.message p {
  margin: 8px 0 0;
  color: #d7e0e8;
  line-height: 1.65;
  white-space: pre-wrap;
}

.empty-runbook-panel {
  max-width: 760px;
}

.starter-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.starter-list li {
  border: 1px solid rgba(var(--color-command-rgb), 0.3);
  border-radius: 999px;
  padding: 6px 10px;
  color: var(--color-command);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  background: rgba(var(--color-command-rgb), 0.08);
}

.command-dock {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid rgba(38, 52, 66, 0.95);
  border-radius: var(--radius-md);
  background: rgba(8, 11, 15, 0.72);
}

.command-dock-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.command-dock input {
  min-width: 0;
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid rgba(38, 52, 66, 1);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: rgba(230, 237, 243, 0.06);
}

.command-dock button {
  min-height: 44px;
  padding: 0 20px;
  color: #071015;
  font-weight: 900;
  background: linear-gradient(135deg, var(--color-agent), #bae6fd);
}

.tool-summary,
.risk-gate-header,
.tool-section-header,
.code-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tool-meta,
.tool-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.tool-section,
.approval-action {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.tool-section button,
.code-block button,
.approval-actions button,
.modal-close {
  min-height: 32px;
  padding: 0 12px;
}

.tool-panel pre,
.code-block pre,
.approval-action pre {
  margin: 0;
  padding: 12px;
  max-height: 260px;
  overflow: auto;
  color: #dce8f3;
  font-family: var(--font-mono);
  white-space: pre-wrap;
  border: 1px solid rgba(38, 52, 66, 0.8);
  border-radius: var(--radius-sm);
  background: rgba(0, 0, 0, 0.28);
}

.risk-gate-status {
  border: 1px solid rgba(var(--color-risk-rgb), 0.46);
  border-radius: 999px;
  padding: 4px 9px;
  color: var(--color-risk);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: rgba(var(--color-risk-rgb), 0.09);
}

.approval-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.approval-actions button:first-child {
  border-color: rgba(52, 211, 153, 0.55);
  color: var(--color-ok);
  background: rgba(52, 211, 153, 0.08);
}

.approval-actions button:last-child {
  border-color: rgba(var(--color-risk-rgb), 0.55);
  color: var(--color-risk);
  background: rgba(var(--color-risk-rgb), 0.08);
}

.markdown-body {
  display: block;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3 {
  margin: 12px 0 8px;
  color: var(--color-text);
  line-height: 1.2;
}

.markdown-body h2 {
  font-size: 1.35rem;
}

.markdown-body p,
.markdown-body ul,
.markdown-body ol {
  color: #d7e0e8;
  line-height: 1.65;
}

.markdown-body table,
.capability-dialog table {
  width: 100%;
  margin: 12px 0;
  border-collapse: collapse;
  overflow: hidden;
  border-radius: var(--radius-sm);
}

.markdown-body th,
.markdown-body td,
.capability-dialog th,
.capability-dialog td {
  padding: 8px 10px;
  border: 1px solid rgba(38, 52, 66, 0.9);
  text-align: left;
  vertical-align: top;
}

.markdown-body th,
.capability-dialog th {
  color: var(--color-text);
  background: rgba(var(--color-command-rgb), 0.1);
}

.markdown-body a {
  color: var(--color-agent);
}

.code-block {
  margin: 12px 0;
  overflow: hidden;
  border: 1px solid rgba(38, 52, 66, 0.95);
  border-radius: var(--radius-sm);
}

.code-block-header {
  padding: 8px 10px;
  color: var(--color-command);
  font-family: var(--font-mono);
  background: rgba(var(--color-command-rgb), 0.08);
}

.inspector-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
  padding: 14px;
}

.inspector-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(38, 52, 66, 0.85);
  border-radius: var(--radius-md);
  background: rgba(230, 237, 243, 0.04);
}

.inspector-list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.inspector-list div {
  display: grid;
  gap: 3px;
}

.inspector-list dt {
  color: var(--color-muted);
  font-size: 0.72rem;
  text-transform: uppercase;
}

.inspector-list dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 0.78rem;
}

.inspector-signal p:last-child {
  margin: 0;
  color: var(--color-agent);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.68);
}

.modal {
  width: min(920px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  overflow: auto;
  padding: 20px;
  border: 1px solid rgba(38, 52, 66, 0.95);
  border-radius: var(--radius-lg);
  background: var(--color-panel-raised);
  box-shadow: var(--shadow-panel);
}

.modal-close {
  margin-top: 16px;
}

.capability-dialog {
  display: grid;
  gap: 12px;
}

.capability-dialog h2 {
  margin: 0;
  color: var(--color-text);
}

.capability-dialog dl {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 8px 14px;
  margin: 0;
}

.capability-dialog dt {
  color: var(--color-muted);
}

.capability-dialog dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}

.cursor::after {
  content: "";
  display: inline-block;
  width: 8px;
  height: 1em;
  margin-left: 4px;
  vertical-align: -2px;
  background: var(--color-agent);
}

@media (max-width: 1120px) {
  .workbench-grid {
    grid-template-columns: minmax(210px, 260px) minmax(0, 1fr);
  }

  .inspector-panel {
    display: none;
  }
}

@media (max-width: 720px) {
  .app-shell {
    overflow: auto;
  }

  .status-strip {
    grid-template-columns: 1fr;
  }

  .workbench-grid {
    grid-template-columns: 1fr;
    overflow: visible;
  }

  .sidebar,
  .chat-pane {
    max-height: none;
  }

  .chat-pane {
    min-height: 70vh;
  }

  .rail-event {
    padding-left: 30px;
  }

  .claw-rail::before {
    left: 10px;
  }

  .rail-event::before {
    left: 3px;
    width: 14px;
    height: 14px;
  }

  .command-dock-row {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}
```

- [ ] **Step 4: Run style tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run src/styles.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run component tests likely affected by CSS-independent structure**

Run:

```bash
cd frontend && npm test -- --run src/components/StatusStrip.test.tsx src/components/InspectorPanel.test.tsx src/components/Sidebar.test.tsx src/components/ChatInput.test.tsx src/components/ChatView.test.tsx src/components/ToolCard.test.tsx src/components/ApprovalCard.test.tsx src/App.test.tsx src/styles.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles.css frontend/src/styles.test.ts
git commit -m "style(frontend): apply obsidian runbook cockpit theme"
```

---

### Task 8: Full frontend verification and integration cleanup

**Files:**
- Modify only files required to fix failures found by the commands in this task.
- Likely files if failures appear: `frontend/src/App.test.tsx`, component tests updated above, or `frontend/src/styles.css`.

**Interfaces:**
- Consumes: all Tasks 1-7.
- Produces: passing frontend test suite and production build.

- [ ] **Step 1: Run the full frontend test suite**

Run:

```bash
cd frontend && npm test -- --run
```

Expected: PASS. If a test fails because accessible names changed, update the test to match the approved Chinese copy from this plan. If a test fails because behavior changed, revert the behavior change and keep the original behavior.

- [ ] **Step 2: Run the production build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS with TypeScript and Vite build output. If TypeScript reports a prop or union type error, fix the component signature rather than loosening types.

- [ ] **Step 3: Run repository status check**

Run:

```bash
git status -sb
```

Expected: only intentional frontend files are modified, or the working tree is clean if every task commit has been made.

- [ ] **Step 4: Commit verification fixes if any were needed**

If Step 1 or Step 2 required code or test fixes, run:

```bash
git add frontend/src
git commit -m "test(frontend): verify runbook cockpit integration"
```

If no files changed during Task 8, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Tokenized Obsidian Runbook palette and fonts: Task 7.
- No external fonts or icons: Global Constraints and Task 7 CSS.
- Claw Rail execution stream: Task 5 and Task 7.
- Top Status Strip: Task 1 and Task 2.
- Runbook Nav: Task 3 and Task 7.
- Execution Stream empty state: Task 5.
- Inspector Panel: Task 1 and Task 2.
- Command Dock: Task 4 and Task 7.
- ToolCard run event styling: Task 6 and Task 7.
- ApprovalCard risk gate styling: Task 6 and Task 7.
- Responsive behavior: Task 7.
- Focus and reduced motion: Task 7.
- Tests and build verification: Task 8.

Type consistency:

- `StatusStripProps` and `InspectorPanel` props use `SessionRecord | null`, `string | null | undefined`, and `status: string` consistently.
- `AppShell` accepts `topbar`, `sidebar`, `inspector`, and `children`, all as `ReactNode`.
- No task changes `MessageBlock`, `SessionRecord`, WebSocket events, or HTTP payload types.

Scope check:

- Theme switching UI and persisted theme preferences are intentionally excluded.
- No backend files are modified.
- No new network requests are introduced.

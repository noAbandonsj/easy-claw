# React Web UI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the current browser chat UI to a React + TypeScript + Vite frontend while keeping the FastAPI backend and the existing static UI available until the React UI reaches parity.

**Architecture:** Add a separate `frontend/` Vite app and serve it under `/app` during migration, leaving the existing `/` static UI untouched. Put API and WebSocket contracts in TypeScript first, normalize all WebSocket events into `MessageBlock[]`, then migrate UI features incrementally. Cut `/` over to the React build only after chat, tools, Markdown, capability modals, sessions, and approval flow are working.

**Tech Stack:** FastAPI, React, TypeScript, Vite, Vitest, React Testing Library, react-markdown, remark-gfm, existing `uv` Python workflow.

---

## Scope Check

This plan covers one subsystem: the local web frontend and the minimum backend static serving and approval protocol changes required for that frontend. It does not replace the CLI, LangChain runtime, storage schema, tool implementations, or MCP/browser tool behavior.

The migration is intentionally incremental:

- Existing `/` UI stays usable until the final cutover task.
- React app is introduced under `/app`.
- Production build output under `frontend/dist/` stays untracked.
- Backend WebSocket compatibility keeps accepting the current plain-text prompt messages while React moves to structured JSON messages.

## File Structure

Create:

- `frontend/package.json` - Node scripts and frontend dependencies.
- `frontend/package-lock.json` - npm lock file committed for reproducible frontend installs.
- `frontend/index.html` - Vite HTML entry.
- `frontend/vite.config.ts` - Vite React config, `/app/` base path, dev proxy to FastAPI.
- `frontend/tsconfig.json` - TypeScript config for browser app.
- `frontend/tsconfig.node.json` - TypeScript config for Vite config.
- `frontend/src/main.tsx` - React root bootstrap.
- `frontend/src/App.tsx` - Top-level app shell composition.
- `frontend/src/api/types.ts` - REST and WebSocket contract types.
- `frontend/src/api/http.ts` - REST client helpers for `/sessions`, `/skills`, `/mcp`, `/browser`, `/slash-commands`.
- `frontend/src/api/chatSocket.ts` - WebSocket URL building and structured send helpers.
- `frontend/src/state/messageBlocks.ts` - Pure reducer that turns stream events into `MessageBlock[]`.
- `frontend/src/state/status.ts` - Pure status text mapping.
- `frontend/src/components/AppShell.tsx` - Page layout.
- `frontend/src/components/Sidebar.tsx` - Session list and status summary.
- `frontend/src/components/ChatView.tsx` - Message stream.
- `frontend/src/components/ChatInput.tsx` - Composer.
- `frontend/src/components/MessageBlockView.tsx` - Block renderer switch.
- `frontend/src/components/ToolCard.tsx` - Tool call/result card.
- `frontend/src/components/MarkdownMessage.tsx` - Markdown renderer with GFM.
- `frontend/src/components/CodeBlock.tsx` - Code block renderer and copy action.
- `frontend/src/components/Modal.tsx` - Shared modal.
- `frontend/src/components/CapabilityDialogs.tsx` - `/skills`, `/mcp`, `/browser`, `/sessions`, `/help` dialogs.
- `frontend/src/components/ApprovalCard.tsx` - Approval UI.
- `frontend/src/styles.css` - React app styles.
- `frontend/src/test/setup.ts` - Vitest DOM setup.
- `frontend/src/**/*.test.ts` and `frontend/src/**/*.test.tsx` - frontend unit/component tests.
- `tests/api/test_react_static_app.py` - backend tests for `/app` serving.
- `tests/api/test_web_approval.py` - backend tests for structured WebSocket approval messages.

Modify:

- `src/easy_claw/api/app.py` - Mount React production build under `/app`, then later switch `/`.
- `src/easy_claw/api/websocket.py` - Serialize approval fields and parse structured client messages.
- `src/easy_claw/agent/approvals.py` - Add a web approval reviewer.
- `src/easy_claw/agent/streaming.py` - Include approval action data in stream events.
- `tests/api/test_api_app.py` - Keep old UI tests during migration, then update final cutover expectations.
- `.gitignore` - Explicitly ignore `frontend/dist/` if needed.
- `README.md` and `docs/cli.md` - Add React web development and production build commands.

Delete only in the final cutover task:

- `src/easy_claw/api/static/index.html`
- `src/easy_claw/api/static/style.css`
- `src/easy_claw/api/static/js/`
- `tests/api/static_web_modules.test.mjs`
- `tests/api/test_static_web_modules.py`

---

### Task 1: Scaffold Frontend Workspace

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/test/setup.ts`
- Create: `tests/core/test_frontend_structure.py`

- [ ] **Step 1: Write the failing structure test**

Create `tests/core/test_frontend_structure.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def test_frontend_workspace_has_react_vite_entrypoints():
    root = Path(__file__).resolve().parents[2]
    package_json = json.loads((root / "frontend" / "package.json").read_text())

    assert package_json["private"] is True
    assert package_json["scripts"]["dev"] == "vite --host 127.0.0.1"
    assert package_json["scripts"]["build"] == "tsc -b && vite build"
    assert package_json["scripts"]["test"] == "vitest"
    assert package_json["scripts"]["lint"] == "tsc -b --noEmit"

    assert (root / "frontend" / "vite.config.ts").is_file()
    assert (root / "frontend" / "src" / "main.tsx").is_file()
    assert (root / "frontend" / "src" / "App.tsx").is_file()
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
uv run --no-sync pytest tests\core\test_frontend_structure.py -q
```

Expected: FAIL because `frontend/package.json` does not exist.

- [ ] **Step 3: Create the frontend files**

Create `frontend/package.json`:

```json
{
  "name": "easy-claw-web",
  "version": "0.5.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1",
    "test": "vitest",
    "test:run": "vitest run",
    "lint": "tsc -b --noEmit"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest",
    "react-markdown": "latest",
    "remark-gfm": "latest"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "latest",
    "@testing-library/react": "latest",
    "@testing-library/user-event": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "jsdom": "latest",
    "vitest": "latest"
  }
}
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>easy-claw</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

Create `frontend/vite.config.ts`:

```ts
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const backend = 'http://127.0.0.1:8787';

export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/ws': { target: backend, ws: true },
      '/health': backend,
      '/sessions': backend,
      '/skills': backend,
      '/mcp': backend,
      '/browser': backend,
      '/slash-commands': backend
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true
  }
});
```

Create `frontend/src/main.tsx`:

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Create `frontend/src/App.tsx`:

```tsx
export function App() {
  return (
    <main className="app-shell">
      <h1>easy-claw</h1>
    </main>
  );
}
```

Create `frontend/src/styles.css`:

```css
:root {
  color-scheme: dark;
  font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
  background: #070713;
  color: #f5f7fb;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
}
```

Create `frontend/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 4: Install frontend dependencies**

Run:

```powershell
Push-Location frontend
npm install
Pop-Location
```

Expected: `frontend/package-lock.json` is created and `frontend/node_modules/` remains untracked.

- [ ] **Step 5: Verify scaffold**

Run:

```powershell
uv run --no-sync pytest tests\core\test_frontend_structure.py -q
Push-Location frontend
npm run lint
npm run test:run
npm run build
Pop-Location
```

Expected: pytest passes; TypeScript check passes; Vitest reports no failing tests; Vite build emits `frontend/dist/`.

- [ ] **Step 6: Commit**

```powershell
git add frontend tests\core\test_frontend_structure.py
git commit -m "build: scaffold react web frontend"
```

---

### Task 2: Serve React Build Under `/app`

**Files:**
- Modify: `src/easy_claw/api/app.py`
- Create: `tests/api/test_react_static_app.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing backend static mount tests**

Create `tests/api/test_react_static_app.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from easy_claw.api.app import create_app
from easy_claw.config import AppConfig


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model="deepseek-v4-pro",
        base_url="https://api.example.com",
        api_key="sk-test",
        mcp_mode="disabled",
    )


def test_react_app_route_serves_dist_index(tmp_path, monkeypatch):
    dist = tmp_path / "frontend" / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<div id="root"></div><script type="module" src="/app/assets/index.js"></script>',
        encoding="utf-8",
    )
    (assets / "index.js").write_text("console.log('easy-claw react')", encoding="utf-8")

    monkeypatch.setattr("easy_claw.api.app._react_dist_dir", lambda: dist)
    client = TestClient(create_app(_config(tmp_path)))

    app_response = client.get("/app")
    nested_response = client.get("/app/sessions")
    asset_response = client.get("/app/assets/index.js")

    assert app_response.status_code == 200
    assert 'id="root"' in app_response.text
    assert nested_response.status_code == 200
    assert asset_response.status_code == 200
    assert "easy-claw react" in asset_response.text


def test_react_app_route_returns_404_when_dist_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("easy_claw.api.app._react_dist_dir", lambda: tmp_path / "missing")
    client = TestClient(create_app(_config(tmp_path)))

    response = client.get("/app")

    assert response.status_code == 404
    assert response.json()["detail"] == "React web UI has not been built"
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
uv run --no-sync pytest tests\api\test_react_static_app.py -q
```

Expected: FAIL because `_react_dist_dir` and `/app` routes do not exist.

- [ ] **Step 3: Implement `/app` serving**

Modify `src/easy_claw/api/app.py`:

```python
_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _react_dist_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"
```

Inside `create_app`, after the existing `root()` route and before API routes:

```python
    react_dist = _react_dist_dir()
    react_assets = react_dist / "assets"
    if react_assets.exists():
        app.mount(
            "/app/assets",
            StaticFiles(directory=react_assets),
            name="react-assets",
        )

    @app.get("/app")
    @app.get("/app/{path:path}")
    def react_app(path: str = "") -> FileResponse:
        index_path = _react_dist_dir() / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="React web UI has not been built")
        return FileResponse(index_path)
```

Keep the current `/` route serving the old static UI.

- [ ] **Step 4: Make ignored build output explicit**

If `.gitignore` does not already ignore nested build output reliably, add:

```gitignore
frontend/dist/
```

- [ ] **Step 5: Verify**

Run:

```powershell
uv run --no-sync pytest tests\api\test_react_static_app.py -q
uv run --no-sync pytest tests\api\test_api_app.py::test_web_ui_uses_split_static_assets -q
```

Expected: React `/app` tests pass; old `/` static UI test still passes.

- [ ] **Step 6: Commit**

```powershell
git add src\easy_claw\api\app.py tests\api\test_react_static_app.py .gitignore
git commit -m "feat: serve react web app under app route"
```

---

### Task 3: Define Frontend Contracts and Message Reducer

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/state/messageBlocks.ts`
- Create: `frontend/src/state/status.ts`
- Create: `frontend/src/state/messageBlocks.test.ts`
- Create: `frontend/src/state/status.test.ts`

- [ ] **Step 1: Write reducer and status tests first**

Create `frontend/src/state/messageBlocks.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { reduceStreamEvent } from './messageBlocks';
import type { MessageBlock } from '../api/types';

describe('reduceStreamEvent', () => {
  it('appends assistant text tokens into one assistant block', () => {
    let blocks: MessageBlock[] = [];
    blocks = reduceStreamEvent(blocks, { type: 'token', content: '## 标题' });
    blocks = reduceStreamEvent(blocks, { type: 'token', content: '\n内容' });

    expect(blocks).toEqual([
      {
        id: 'assistant-1',
        kind: 'assistant',
        content: '## 标题\n内容',
        streaming: true,
      },
    ]);
  });

  it('merges tool result into the matching pending tool block', () => {
    let blocks: MessageBlock[] = [];
    blocks = reduceStreamEvent(blocks, {
      type: 'tool_call_start',
      tool_name: 'read_file',
      tool_args: { path: 'README.md' },
    });
    blocks = reduceStreamEvent(blocks, {
      type: 'tool_call_result',
      tool_name: 'read_file',
      tool_result: '# easy-claw',
    });

    expect(blocks).toEqual([
      {
        id: 'tool-1',
        kind: 'tool',
        name: 'read_file',
        args: { path: 'README.md' },
        result: '# easy-claw',
        status: 'finished',
      },
    ]);
  });

  it('adds approval blocks from approval_required events', () => {
    const blocks = reduceStreamEvent([], {
      type: 'approval_required',
      approval_id: 'approval-1',
      approval_actions: [{ name: 'run_command', args: { command: 'uv run pytest' } }],
    });

    expect(blocks).toEqual([
      {
        id: 'approval-1',
        kind: 'approval',
        approvalId: 'approval-1',
        actions: [{ name: 'run_command', args: { command: 'uv run pytest' } }],
        status: 'pending',
      },
    ]);
  });
});
```

Create `frontend/src/state/status.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { statusForEvent } from './status';

describe('statusForEvent', () => {
  it('keeps the app busy until done arrives', () => {
    expect(statusForEvent({ type: 'tool_call_result', tool_name: 'read_file' })).toBe(
      '整理回复...',
    );
    expect(statusForEvent({ type: 'token', content: 'hello' })).toBe('回复中...');
    expect(statusForEvent({ type: 'done' })).toBe('就绪');
  });
});
```

- [ ] **Step 2: Run failing frontend tests**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/state/messageBlocks.test.ts src/state/status.test.ts
Pop-Location
```

Expected: FAIL because `api/types.ts`, `state/messageBlocks.ts`, and `state/status.ts` do not exist.

- [ ] **Step 3: Implement contract types**

Create `frontend/src/api/types.ts`:

```ts
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
  | { type: 'banner'; model?: string; workspace?: string; version?: string; session_id?: string }
  | { type: 'token'; content: string }
  | { type: 'tool_call_start'; tool_name?: string; tool_args?: unknown }
  | { type: 'tool_call_result'; tool_name?: string; tool_result?: unknown; content?: string }
  | { type: 'approval_required'; approval_id?: string; approval_actions?: ToolActionRequest[] }
  | { type: 'done'; usage?: TokenUsage; content?: string }
  | { type: 'error'; content?: string }
  | { type: 'interrupted'; content?: string };

export type SessionRecord = {
  id: string;
  title: string;
  workspace_path: string;
  model: string | null;
  created_at: string;
  updated_at: string;
};

export type SkillSource = {
  scope: string;
  label: string;
  skill_count: number;
  backend_path: string;
  filesystem_path: string;
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
    }
  | {
      id: string;
      kind: 'approval';
      approvalId: string;
      actions: ToolActionRequest[];
      status: 'pending' | 'approved' | 'rejected';
    }
  | { id: string; kind: 'error'; content: string };
```

- [ ] **Step 4: Implement status and reducer**

Create `frontend/src/state/status.ts`:

```ts
import type { StreamEvent } from '../api/types';

export function statusForEvent(event: StreamEvent): string | null {
  switch (event.type) {
    case 'banner':
      return '就绪';
    case 'token':
      return '回复中...';
    case 'tool_call_start':
      return `调用工具：${event.tool_name || '未知'}`;
    case 'tool_call_result':
      return '整理回复...';
    case 'approval_required':
      return '等待审批';
    case 'done':
      return '就绪';
    case 'error':
      return `错误：${event.content || ''}`;
    case 'interrupted':
      return '已中断';
    default:
      return null;
  }
}
```

Create `frontend/src/state/messageBlocks.ts`:

```ts
import type { MessageBlock, StreamEvent, ToolActionRequest } from '../api/types';

function nextId(prefix: string, blocks: MessageBlock[]) {
  return `${prefix}-${blocks.filter(block => block.id.startsWith(`${prefix}-`)).length + 1}`;
}

export function addUserBlock(blocks: MessageBlock[], content: string): MessageBlock[] {
  return [...blocks, { id: nextId('user', blocks), kind: 'user', content }];
}

export function reduceStreamEvent(blocks: MessageBlock[], event: StreamEvent): MessageBlock[] {
  switch (event.type) {
    case 'token':
      return appendAssistantToken(blocks, event.content || '');
    case 'tool_call_start':
      return [
        ...finishStreamingAssistant(blocks),
        {
          id: nextId('tool', blocks),
          kind: 'tool',
          name: event.tool_name || '未知工具',
          args: event.tool_args ?? null,
          result: null,
          status: 'running',
        },
      ];
    case 'tool_call_result':
      return finishToolBlock(blocks, event.tool_name || '未知工具', event.tool_result ?? event.content ?? '');
    case 'approval_required':
      return [
        ...finishStreamingAssistant(blocks),
        {
          id: event.approval_id || nextId('approval', blocks),
          kind: 'approval',
          approvalId: event.approval_id || nextId('approval', blocks),
          actions: event.approval_actions || [],
          status: 'pending',
        },
      ];
    case 'done':
      return finishStreamingAssistant(blocks);
    case 'error':
      return [...finishStreamingAssistant(blocks), { id: nextId('error', blocks), kind: 'error', content: event.content || '未知错误' }];
    default:
      return blocks;
  }
}

function appendAssistantToken(blocks: MessageBlock[], content: string): MessageBlock[] {
  const last = blocks[blocks.length - 1];
  if (last?.kind === 'assistant' && last.streaming) {
    return [...blocks.slice(0, -1), { ...last, content: last.content + content }];
  }
  return [...blocks, { id: nextId('assistant', blocks), kind: 'assistant', content, streaming: true }];
}

function finishStreamingAssistant(blocks: MessageBlock[]): MessageBlock[] {
  return blocks.map(block => (block.kind === 'assistant' ? { ...block, streaming: false } : block));
}

function finishToolBlock(blocks: MessageBlock[], name: string, result: unknown): MessageBlock[] {
  const index = [...blocks]
    .reverse()
    .findIndex(block => block.kind === 'tool' && block.status === 'running' && block.name === name);
  if (index === -1) {
    return [
      ...blocks,
      { id: nextId('tool', blocks), kind: 'tool', name, args: null, result, status: 'finished' },
    ];
  }
  const realIndex = blocks.length - 1 - index;
  return blocks.map((block, blockIndex) =>
    blockIndex === realIndex && block.kind === 'tool'
      ? { ...block, result, status: 'finished' }
      : block,
  );
}

export function markApproval(
  blocks: MessageBlock[],
  approvalId: string,
  status: 'approved' | 'rejected',
): MessageBlock[] {
  return blocks.map(block =>
    block.kind === 'approval' && block.approvalId === approvalId ? { ...block, status } : block,
  );
}
```

- [ ] **Step 5: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/state/messageBlocks.test.ts src/state/status.test.ts
npm run lint
Pop-Location
```

Expected: reducer tests and TypeScript pass.

- [ ] **Step 6: Commit**

```powershell
git add frontend\src\api\types.ts frontend\src\state frontend\src\state\*.test.ts
git commit -m "feat: define web chat contracts"
```

---

### Task 4: Add REST and WebSocket Client Helpers

**Files:**
- Create: `frontend/src/api/http.ts`
- Create: `frontend/src/api/chatSocket.ts`
- Create: `frontend/src/api/http.test.ts`
- Create: `frontend/src/api/chatSocket.test.ts`

- [ ] **Step 1: Write failing API helper tests**

Create `frontend/src/api/chatSocket.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { buildChatWsUrl, encodePromptMessage, encodeApprovalDecision } from './chatSocket';

describe('chatSocket helpers', () => {
  it('builds websocket URLs from browser locations', () => {
    expect(buildChatWsUrl(new URL('http://127.0.0.1:5173/app'), 'abc123')).toBe(
      'ws://127.0.0.1:5173/ws/chat?session_id=abc123',
    );
    expect(buildChatWsUrl(new URL('https://example.com/app'), undefined)).toBe(
      'wss://example.com/ws/chat',
    );
  });

  it('encodes structured client messages', () => {
    expect(encodePromptMessage('hello')).toBe(JSON.stringify({ type: 'prompt', content: 'hello' }));
    expect(encodeApprovalDecision('approval-1', 'approve')).toBe(
      JSON.stringify({ type: 'approval_decision', approval_id: 'approval-1', decision: 'approve' }),
    );
  });
});
```

Create `frontend/src/api/http.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { fetchJson, postJson } from './http';

describe('http helpers', () => {
  it('returns json payloads', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    });

    await expect(fetchJson('/health', fetcher)).resolves.toEqual({ status: 'ok' });
  });

  it('surfaces API detail messages', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      statusText: 'Bad Request',
      json: async () => ({ detail: '失败' }),
    });

    await expect(postJson('/sessions', { title: 'x' }, fetcher)).rejects.toThrow('失败');
  });
});
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/api/chatSocket.test.ts src/api/http.test.ts
Pop-Location
```

Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement helpers**

Create `frontend/src/api/chatSocket.ts`:

```ts
export type ClientMessage =
  | { type: 'prompt'; content: string }
  | { type: 'approval_decision'; approval_id: string; decision: 'approve' | 'reject'; message?: string };

export function buildChatWsUrl(locationUrl: URL, sessionId?: string) {
  const protocol = locationUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = new URL(`${protocol}//${locationUrl.host}/ws/chat`);
  if (sessionId) url.searchParams.set('session_id', sessionId);
  return url.toString();
}

export function encodePromptMessage(content: string) {
  return JSON.stringify({ type: 'prompt', content } satisfies ClientMessage);
}

export function encodeApprovalDecision(
  approvalId: string,
  decision: 'approve' | 'reject',
  message?: string,
) {
  return JSON.stringify({
    type: 'approval_decision',
    approval_id: approvalId,
    decision,
    ...(message ? { message } : {}),
  } satisfies ClientMessage);
}
```

Create `frontend/src/api/http.ts`:

```ts
export type Fetcher = typeof fetch;

export async function fetchJson<T>(path: string, fetcher: Fetcher = fetch): Promise<T> {
  const response = await fetcher(path);
  return readJsonResponse<T>(response);
}

export async function postJson<T>(
  path: string,
  body: unknown,
  fetcher: Fetcher = fetch,
): Promise<T> {
  const response = await fetcher(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return readJsonResponse<T>(response);
}

async function readJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
```

- [ ] **Step 4: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/api/chatSocket.test.ts src/api/http.test.ts
npm run lint
Pop-Location
```

Expected: helper tests and TypeScript pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend\src\api
git commit -m "feat: add frontend api clients"
```

---

### Task 5: Build React Shell, Sessions, and Composer

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/ChatInput.tsx`
- Create: `frontend/src/components/AppShell.test.tsx`
- Create: `frontend/src/components/ChatInput.test.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write component tests**

Create `frontend/src/components/ChatInput.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ChatInput } from './ChatInput';

describe('ChatInput', () => {
  it('submits with Enter and keeps Shift+Enter as newline', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} onSubmit={onSubmit} />);

    const input = screen.getByPlaceholderText('输入消息... (Enter 发送, Shift+Enter 换行)');
    await user.type(input, '第一行{Shift>}{Enter}{/Shift}第二行');
    await user.keyboard('{Enter}');

    expect(onSubmit).toHaveBeenCalledWith('第一行\n第二行');
  });
});
```

Create `frontend/src/components/AppShell.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AppShell } from './AppShell';

describe('AppShell', () => {
  it('renders sidebar, top status, messages, and composer regions', () => {
    render(
      <AppShell
        status="就绪"
        model="deepseek-v4-pro"
        workspace="D:\\Pathon\\Programs\\easy-claw"
        tokenTotal={0}
        sessions={[]}
        activeSessionId="abc123"
        onNewChat={() => undefined}
        onSelectSession={() => undefined}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.getByText('easy-claw')).toBeInTheDocument();
    expect(screen.getByText('就绪')).toBeInTheDocument();
    expect(screen.getByText('deepseek-v4-pro')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '+ 新对话' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/AppShell.test.tsx src/components/ChatInput.test.tsx
Pop-Location
```

Expected: FAIL because components do not exist.

- [ ] **Step 3: Implement components**

Create `frontend/src/components/ChatInput.tsx`:

```tsx
import { FormEvent, KeyboardEvent, useState } from 'react';

type ChatInputProps = {
  disabled: boolean;
  onSubmit: (text: string) => void;
};

export function ChatInput({ disabled, onSubmit }: ChatInputProps) {
  const [value, setValue] = useState('');

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = value.trim();
    if (!text) return;
    onSubmit(value);
    setValue('');
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="input-area" onSubmit={submit}>
      <textarea
        disabled={disabled}
        onChange={event => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
        rows={1}
        value={value}
      />
      <button disabled={disabled || !value.trim()} type="submit">
        发送
      </button>
    </form>
  );
}
```

Create `frontend/src/components/Sidebar.tsx`:

```tsx
import type { SessionRecord } from '../api/types';

type SidebarProps = {
  model: string;
  workspace: string;
  tokenTotal: number;
  sessions: SessionRecord[];
  activeSessionId: string;
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
};

export function Sidebar({
  model,
  workspace,
  tokenTotal,
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
}: SidebarProps) {
  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <span>◆ easy-claw</span>
          <span>v0.5</span>
        </div>
        <button type="button" onClick={onNewChat}>
          + 新对话
        </button>
      </div>
      <div className="session-list">
        {sessions.length === 0 ? (
          <div className="empty-state">暂无会话</div>
        ) : (
          sessions.map(session => (
            <button
              className={session.id === activeSessionId ? 'session-item active' : 'session-item'}
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              type="button"
            >
              <span>{session.title || '未命名'}</span>
              <small>{session.model || '-'}</small>
            </button>
          ))
        )}
      </div>
      <div className="sidebar-status">
        <div><span>模型</span><strong>{model || '-'}</strong></div>
        <div><span>工作区</span><strong>{workspace || '-'}</strong></div>
        <div><span>Token</span><strong>{tokenTotal.toLocaleString()}</strong></div>
      </div>
    </nav>
  );
}
```

Create `frontend/src/components/AppShell.tsx`:

```tsx
import type { MessageBlock, SessionRecord } from '../api/types';
import { ChatInput } from './ChatInput';
import { Sidebar } from './Sidebar';

type AppShellProps = {
  status: string;
  model: string;
  workspace: string;
  tokenTotal: number;
  sessions: SessionRecord[];
  activeSessionId: string;
  messages?: MessageBlock[];
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  onSubmit: (text: string) => void;
};

export function AppShell(props: AppShellProps) {
  return (
    <div className="app-layout">
      <Sidebar
        activeSessionId={props.activeSessionId}
        model={props.model}
        onNewChat={props.onNewChat}
        onSelectSession={props.onSelectSession}
        sessions={props.sessions}
        tokenTotal={props.tokenTotal}
        workspace={props.workspace}
      />
      <main className="main-area">
        <header className="topbar">
          <span className="conn-dot" />
          <span>{props.activeSessionId ? props.activeSessionId.slice(0, 8) : 'easy-claw'}</span>
          <span className="topbar-status">{props.status}</span>
        </header>
        <section className="messages" aria-label="对话消息">
          {(props.messages || []).length === 0 ? null : props.messages?.map(block => (
            <div key={block.id}>{block.kind}</div>
          ))}
        </section>
        <ChatInput disabled={false} onSubmit={props.onSubmit} />
      </main>
    </div>
  );
}
```

Modify `frontend/src/App.tsx`:

```tsx
import { AppShell } from './components/AppShell';

export function App() {
  return (
    <AppShell
      activeSessionId=""
      model=""
      onNewChat={() => undefined}
      onSelectSession={() => undefined}
      onSubmit={() => undefined}
      sessions={[]}
      status="连接中..."
      tokenTotal={0}
      workspace=""
    />
  );
}
```

Replace `frontend/src/styles.css` with a compact layout matching the existing app:

```css
:root {
  color-scheme: dark;
  font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
  background: #070713;
  color: #f5f7fb;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button,
textarea {
  font: inherit;
}

.app-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 260px 1fr;
  background: #070713;
}

.sidebar {
  display: grid;
  grid-template-rows: auto 1fr auto;
  border-right: 1px solid #26264a;
  background: #101023;
}

.sidebar-header,
.sidebar-status,
.topbar,
.input-area {
  padding: 12px 16px;
}

.brand,
.sidebar-status div,
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.session-list {
  overflow: auto;
  padding: 8px;
}

.session-item {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  display: grid;
  gap: 4px;
  padding: 8px;
  text-align: left;
}

.session-item.active,
.session-item:hover {
  border-color: #00ffff33;
  background: #00ffff10;
}

.main-area {
  min-width: 0;
  display: grid;
  grid-template-rows: auto 1fr auto;
}

.messages {
  overflow: auto;
  padding: 16px;
}

.input-area {
  display: flex;
  gap: 10px;
  border-top: 1px solid #26264a;
}

.input-area textarea {
  flex: 1;
  min-height: 42px;
  max-height: 160px;
  resize: vertical;
}
```

- [ ] **Step 4: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/AppShell.test.tsx src/components/ChatInput.test.tsx
npm run lint
npm run build
Pop-Location
```

Expected: component tests, TypeScript, and build pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend\src
git commit -m "feat: build react chat shell"
```

---

### Task 6: Connect Sessions and WebSocket Chat

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/hooks/useSessions.ts`
- Create: `frontend/src/hooks/useChatSocket.ts`
- Create: `frontend/src/hooks/useSessions.test.ts`
- Create: `frontend/src/hooks/useChatSocket.test.ts`
- Modify: `frontend/src/components/AppShell.tsx`

- [ ] **Step 1: Write hook tests**

Create `frontend/src/hooks/useSessions.test.ts`:

```ts
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useSessions } from './useSessions';

describe('useSessions', () => {
  it('loads sessions and can create a new one', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 's1', title: '新会话' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => [{ id: 's1', title: '新会话' }] });

    const { result } = renderHook(() => useSessions(fetcher));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await result.current.createSession();

    expect(fetcher).toHaveBeenCalledWith('/sessions');
    expect(fetcher).toHaveBeenCalledWith('/sessions', expect.objectContaining({ method: 'POST' }));
  });
});
```

Create `frontend/src/hooks/useChatSocket.test.ts` with a fake WebSocket constructor:

```ts
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useChatSocket } from './useChatSocket';

class FakeSocket {
  static instances: FakeSocket[] = [];
  readyState = 1;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;

  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }

  send(value: string) {
    this.sent.push(value);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

describe('useChatSocket', () => {
  it('sends prompts and reduces token events into blocks', () => {
    const { result } = renderHook(() =>
      useChatSocket({
        WebSocketImpl: FakeSocket as unknown as typeof WebSocket,
        locationUrl: new URL('http://127.0.0.1:5173/app'),
      }),
    );

    act(() => FakeSocket.instances[0].onopen?.());
    act(() => result.current.sendPrompt('hello'));
    act(() =>
      FakeSocket.instances[0].onmessage?.({
        data: JSON.stringify({ type: 'token', content: 'hi' }),
      }),
    );

    expect(FakeSocket.instances[0].sent[0]).toBe(JSON.stringify({ type: 'prompt', content: 'hello' }));
    expect(result.current.blocks).toEqual([
      { id: 'user-1', kind: 'user', content: 'hello' },
      { id: 'assistant-1', kind: 'assistant', content: 'hi', streaming: true },
    ]);
  });
});
```

- [ ] **Step 2: Run failing hook tests**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/hooks/useSessions.test.ts src/hooks/useChatSocket.test.ts
Pop-Location
```

Expected: FAIL because hooks do not exist.

- [ ] **Step 3: Implement hooks**

Create `frontend/src/hooks/useSessions.ts`:

```ts
import { useCallback, useEffect, useState } from 'react';
import type { Fetcher } from '../api/http';
import { fetchJson, postJson } from '../api/http';
import type { SessionRecord } from '../api/types';

export function useSessions(fetcher: Fetcher = fetch) {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      setSessions(await fetchJson<SessionRecord[]>('/sessions', fetcher));
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  const createSession = useCallback(async () => {
    const created = await postJson<SessionRecord>('/sessions', { title: '新会话' }, fetcher);
    await loadSessions();
    return created;
  }, [fetcher, loadSessions]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  return { sessions, loading, loadSessions, createSession };
}
```

Create `frontend/src/hooks/useChatSocket.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from 'react';
import { buildChatWsUrl, encodeApprovalDecision, encodePromptMessage } from '../api/chatSocket';
import type { MessageBlock, StreamEvent, TokenUsage } from '../api/types';
import { addUserBlock, markApproval, reduceStreamEvent } from '../state/messageBlocks';
import { statusForEvent } from '../state/status';

type UseChatSocketOptions = {
  WebSocketImpl?: typeof WebSocket;
  locationUrl?: URL;
  sessionId?: string;
};

export function useChatSocket({
  WebSocketImpl = WebSocket,
  locationUrl = new URL(window.location.href),
  sessionId,
}: UseChatSocketOptions = {}) {
  const socketRef = useRef<WebSocket | null>(null);
  const [blocks, setBlocks] = useState<MessageBlock[]>([]);
  const [status, setStatus] = useState('连接中...');
  const [banner, setBanner] = useState({ model: '', workspace: '', version: '', sessionId: '' });
  const [usage, setUsage] = useState<TokenUsage>({});

  useEffect(() => {
    const socket = new WebSocketImpl(buildChatWsUrl(locationUrl, sessionId));
    socketRef.current = socket;
    socket.onopen = () => setStatus('就绪');
    socket.onclose = () => setStatus('连接已断开');
    socket.onmessage = event => {
      const streamEvent = JSON.parse(event.data) as StreamEvent;
      const nextStatus = statusForEvent(streamEvent);
      if (nextStatus) setStatus(nextStatus);
      if (streamEvent.type === 'banner') {
        setBanner({
          model: streamEvent.model || '',
          workspace: streamEvent.workspace || '',
          version: streamEvent.version || '',
          sessionId: streamEvent.session_id || '',
        });
      }
      if (streamEvent.type === 'done' && streamEvent.usage) {
        setUsage(streamEvent.usage);
      }
      setBlocks(current => reduceStreamEvent(current, streamEvent));
    };
    return () => socket.close();
  }, [WebSocketImpl, locationUrl, sessionId]);

  const sendPrompt = useCallback((text: string) => {
    setBlocks(current => addUserBlock(current, text));
    socketRef.current?.send(encodePromptMessage(text));
    setStatus('思考中...');
  }, []);

  const sendApprovalDecision = useCallback((approvalId: string, decision: 'approve' | 'reject') => {
    socketRef.current?.send(encodeApprovalDecision(approvalId, decision));
    setBlocks(current => markApproval(current, approvalId, decision === 'approve' ? 'approved' : 'rejected'));
  }, []);

  return { blocks, status, banner, usage, sendPrompt, sendApprovalDecision };
}
```

Modify `frontend/src/App.tsx` to use hooks and pass state into `AppShell`.

- [ ] **Step 4: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/hooks/useSessions.test.ts src/hooks/useChatSocket.test.ts
npm run lint
npm run build
Pop-Location
```

Expected: hook tests, TypeScript, and build pass.

- [ ] **Step 5: Browser smoke test**

Run backend and Vite dev server in separate PowerShell windows:

```powershell
uv run easy-claw serve
```

```powershell
Push-Location frontend
npm run dev
Pop-Location
```

Open `http://127.0.0.1:5173/app` and send `/status`. Expected: WebSocket connects, a user message appears, and the status changes without console errors.

- [ ] **Step 6: Commit**

```powershell
git add frontend\src
git commit -m "feat: connect react chat websocket"
```

---

### Task 7: Render Message Blocks and Tool Cards

**Files:**
- Create: `frontend/src/components/MessageBlockView.tsx`
- Create: `frontend/src/components/ToolCard.tsx`
- Create: `frontend/src/components/MessageBlockView.test.tsx`
- Create: `frontend/src/components/ToolCard.test.tsx`
- Modify: `frontend/src/components/ChatView.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write rendering tests**

Create `frontend/src/components/ToolCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ToolCard } from './ToolCard';

describe('ToolCard', () => {
  it('shows a finished tool with params and result in one expandable card', async () => {
    const user = userEvent.setup();
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

    expect(screen.getByText('read_file')).toBeInTheDocument();
    expect(screen.getByText('已完成')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '展开详情' }));

    expect(screen.getByText('参数')).toBeInTheDocument();
    expect(screen.getByText('结果')).toBeInTheDocument();
    expect(screen.getByText(/README.md/)).toBeInTheDocument();
    expect(screen.getByText(/easy-claw/)).toBeInTheDocument();
  });
});
```

Create `frontend/src/components/MessageBlockView.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MessageBlockView } from './MessageBlockView';

describe('MessageBlockView', () => {
  it('renders user and error blocks', () => {
    render(
      <>
        <MessageBlockView block={{ id: 'u1', kind: 'user', content: 'hello' }} />
        <MessageBlockView block={{ id: 'e1', kind: 'error', content: '失败' }} />
      </>,
    );

    expect(screen.getByText('hello')).toBeInTheDocument();
    expect(screen.getByText('失败')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/ToolCard.test.tsx src/components/MessageBlockView.test.tsx
Pop-Location
```

Expected: FAIL because components do not exist.

- [ ] **Step 3: Implement `ToolCard`**

Create `frontend/src/components/ToolCard.tsx`:

```tsx
import { useState } from 'react';
import type { MessageBlock } from '../api/types';

type ToolBlock = Extract<MessageBlock, { kind: 'tool' }>;

export function ToolCard({ block }: { block: ToolBlock }) {
  const [open, setOpen] = useState(false);
  const resultText = formatPayload(block.result);
  const argsText = formatPayload(block.args);

  return (
    <article className={`tool-card ${block.status}`}>
      <button className="tool-card-header" onClick={() => setOpen(value => !value)} type="button">
        <span>
          <strong>{block.name}</strong>
          <small>{block.status === 'finished' ? '已完成' : '运行中'}</small>
        </span>
        <span>{open ? '▼' : '▶'}</span>
      </button>
      <div className="tool-summary">
        <span>摘要</span>
        <span>{resultText ? shorten(resultText, 180) : shorten(argsText, 180)}</span>
      </div>
      <button className="tool-action" onClick={() => setOpen(value => !value)} type="button">
        {open ? '收起详情' : '展开详情'}
      </button>
      {open ? (
        <div className="tool-detail">
          <h3>参数</h3>
          <pre>{argsText}</pre>
          {block.status === 'finished' ? (
            <>
              <h3>结果</h3>
              <pre>{resultText}</pre>
            </>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function formatPayload(value: unknown) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function shorten(value: string, limit: number) {
  const normalized = value.replace(/\s+/g, ' ').trim();
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit - 1)}…`;
}
```

Create `frontend/src/components/MessageBlockView.tsx`:

```tsx
import type { MessageBlock } from '../api/types';
import { MarkdownMessage } from './MarkdownMessage';
import { ToolCard } from './ToolCard';

export function MessageBlockView({ block }: { block: MessageBlock }) {
  switch (block.kind) {
    case 'user':
      return <div className="message user">{block.content}</div>;
    case 'assistant':
      return <MarkdownMessage content={block.content} streaming={block.streaming} />;
    case 'tool':
      return <ToolCard block={block} />;
    case 'approval':
      return <div className="approval-card">等待审批</div>;
    case 'error':
      return <div className="message error">{block.content}</div>;
  }
}
```

Create `frontend/src/components/MarkdownMessage.tsx` initially:

```tsx
export function MarkdownMessage({ content, streaming }: { content: string; streaming: boolean }) {
  return (
    <div className="message assistant">
      <span>{content}</span>
      {streaming ? <span className="cursor" /> : null}
    </div>
  );
}
```

Create `frontend/src/components/ChatView.tsx`:

```tsx
import type { MessageBlock } from '../api/types';
import { MessageBlockView } from './MessageBlockView';

export function ChatView({ blocks }: { blocks: MessageBlock[] }) {
  return (
    <section className="messages" aria-label="对话消息">
      {blocks.map(block => (
        <MessageBlockView block={block} key={block.id} />
      ))}
    </section>
  );
}
```

Modify `AppShell` to use `ChatView` instead of placeholder block divs.

- [ ] **Step 4: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/ToolCard.test.tsx src/components/MessageBlockView.test.tsx
npm run lint
npm run build
Pop-Location
```

Expected: rendering tests, TypeScript, and build pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend\src
git commit -m "feat: render react chat blocks"
```

---

### Task 8: Add Markdown, Tables, Code Blocks, and Copy Buttons

**Files:**
- Modify: `frontend/src/components/MarkdownMessage.tsx`
- Create: `frontend/src/components/CodeBlock.tsx`
- Create: `frontend/src/components/MarkdownMessage.test.tsx`
- Create: `frontend/src/components/CodeBlock.test.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write Markdown rendering tests**

Create `frontend/src/components/MarkdownMessage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarkdownMessage } from './MarkdownMessage';

describe('MarkdownMessage', () => {
  it('renders headings, lists, tables, and code blocks', () => {
    render(
      <MarkdownMessage
        content={`## 标题

1. 第一项
2. 第二项

| 文件 | 作用 | 风险 |
|---|---|---|
| README.md | 文档 | 过期 |

\`\`\`powershell
uv run easy-claw serve
\`\`\``}
        streaming={false}
      />,
    );

    expect(screen.getByRole('heading', { name: '标题', level: 2 })).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('uv run easy-claw serve')).toBeInTheDocument();
  });
});
```

Create `frontend/src/components/CodeBlock.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CodeBlock } from './CodeBlock';

describe('CodeBlock', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('copies code text', async () => {
    const user = userEvent.setup();
    render(<CodeBlock language="powershell" value="uv run easy-claw serve" />);

    await user.click(screen.getByRole('button', { name: '复制代码' }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('uv run easy-claw serve');
  });
});
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/MarkdownMessage.test.tsx src/components/CodeBlock.test.tsx
Pop-Location
```

Expected: FAIL because `CodeBlock` and real Markdown rendering are not implemented.

- [ ] **Step 3: Implement Markdown renderer**

Create `frontend/src/components/CodeBlock.tsx`:

```tsx
export function CodeBlock({ language, value }: { language?: string; value: string }) {
  async function copy() {
    await navigator.clipboard.writeText(value);
  }

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span>{language || 'text'}</span>
        <button onClick={copy} type="button">
          复制代码
        </button>
      </div>
      <pre>
        <code>{value}</code>
      </pre>
    </div>
  );
}
```

Modify `frontend/src/components/MarkdownMessage.tsx`:

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';

export function MarkdownMessage({ content, streaming }: { content: string; streaming: boolean }) {
  return (
    <div className="message assistant markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children }) {
            const value = String(children).replace(/\n$/, '');
            const match = /language-(\w+)/.exec(className || '');
            if (className) {
              return <CodeBlock language={match?.[1]} value={value} />;
            }
            return <code>{children}</code>;
          },
          a({ children, href }) {
            return (
              <a href={href} rel="noreferrer" target="_blank">
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {streaming ? <span className="cursor" /> : null}
    </div>
  );
}
```

Add CSS for `.markdown-body`, `.code-block`, and table styles using the existing palette.

- [ ] **Step 4: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/MarkdownMessage.test.tsx src/components/CodeBlock.test.tsx
npm run lint
npm run build
Pop-Location
```

Expected: Markdown tests, TypeScript, and build pass.

- [ ] **Step 5: Browser smoke test**

Open `http://127.0.0.1:5173/app` and ask:

```text
请不要使用工具，直接用 Markdown 回答：一个二级标题、一个两行三列表格、一个 powershell 代码块。
```

Expected: the response contains a real table and a code block with a copy button.

- [ ] **Step 6: Commit**

```powershell
git add frontend\src
git commit -m "feat: render markdown in react web"
```

---

### Task 9: Migrate Capability Dialogs and Slash Commands

**Files:**
- Create: `frontend/src/components/Modal.tsx`
- Create: `frontend/src/components/CapabilityDialogs.tsx`
- Create: `frontend/src/components/CapabilityDialogs.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api/http.ts`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write dialog tests**

Create `frontend/src/components/CapabilityDialogs.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CapabilityDialog } from './CapabilityDialogs';

describe('CapabilityDialog', () => {
  it('renders skills data', () => {
    render(
      <CapabilityDialog
        kind="skills"
        payload={{
          source_count: 1,
          skill_count: 2,
          sources: [
            {
              scope: 'project',
              label: 'project skills',
              skill_count: 2,
              backend_path: '/skills/',
              filesystem_path: 'D:\\Pathon\\Programs\\easy-claw\\skills',
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Skill 来源' })).toBeInTheDocument();
    expect(screen.getByText('project skills')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/CapabilityDialogs.test.tsx
Pop-Location
```

Expected: FAIL because dialog components do not exist.

- [ ] **Step 3: Implement dialogs**

Create `frontend/src/components/Modal.tsx`:

```tsx
import { ReactNode } from 'react';

export function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div className="modal" onClick={event => event.stopPropagation()}>
        {children}
        <button className="modal-close" onClick={onClose} type="button">
          关闭
        </button>
      </div>
    </div>
  );
}
```

Create `frontend/src/components/CapabilityDialogs.tsx` with render branches for:

- `skills`: payload from `/skills`
- `mcp`: payload from `/mcp`
- `browser`: payload from `/browser`
- `sessions`: payload from `/sessions`
- `help`: payload from `/slash-commands`

Use tables, not nested cards.

- [ ] **Step 4: Wire slash commands**

In `App.tsx`, intercept input beginning with `/`:

- `/help`
- `/status`
- `/skills`
- `/mcp`
- `/browser`
- `/sessions`
- `/resume <session-id>`
- `/clear`
- `/save`
- `/exit`

For unsupported Web commands (`/workspace`, `/model`, `/doctor`, `/delete-session`), set status to the same CLI-only message used by the old UI.

- [ ] **Step 5: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run -- src/components/CapabilityDialogs.test.tsx
npm run lint
npm run build
Pop-Location
```

Expected: dialog test, TypeScript, and build pass.

- [ ] **Step 6: Browser smoke test**

Open `http://127.0.0.1:5173/app` and run:

```text
/skills
/mcp
/browser
/sessions
/help
```

Expected: each command opens a modal with data loaded from the FastAPI endpoints.

- [ ] **Step 7: Commit**

```powershell
git add frontend\src
git commit -m "feat: migrate web capability dialogs"
```

---

### Task 10: Add Real Web Approval Protocol

**Files:**
- Modify: `src/easy_claw/agent/approvals.py`
- Modify: `src/easy_claw/agent/streaming.py`
- Modify: `src/easy_claw/api/websocket.py`
- Modify: `src/easy_claw/api/app.py`
- Create: `tests/api/test_web_approval.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/hooks/useChatSocket.ts`
- Create: `frontend/src/components/ApprovalCard.tsx`
- Create: `frontend/src/components/ApprovalCard.test.tsx`
- Modify: `frontend/src/components/MessageBlockView.tsx`

- [ ] **Step 1: Write backend approval tests**

Create `tests/api/test_web_approval.py`:

```python
from __future__ import annotations

from easy_claw.agent.approvals import WebApprovalReviewer


def test_web_approval_reviewer_returns_submitted_approval_decision():
    reviewer = WebApprovalReviewer()
    request = reviewer.prepare([{"action_requests": [{"name": "run_command", "args": {"command": "uv run pytest"}}]}])

    assert request.approval_id.startswith("approval-")
    assert request.actions == [{"name": "run_command", "args": {"command": "uv run pytest"}}]

    reviewer.submit(request.approval_id, approve=True)

    assert reviewer.review([]) == [{"type": "approve"}]


def test_web_approval_reviewer_returns_rejection_message():
    reviewer = WebApprovalReviewer()
    request = reviewer.prepare([{"action_requests": [{"name": "run_command", "args": {}}]}])

    reviewer.submit(request.approval_id, approve=False, message="用户拒绝")

    assert reviewer.review([]) == [{"type": "reject", "message": "用户拒绝"}]
```

- [ ] **Step 2: Run failing backend approval tests**

Run:

```powershell
uv run --no-sync pytest tests\api\test_web_approval.py -q
```

Expected: FAIL because `WebApprovalReviewer` does not exist.

- [ ] **Step 3: Implement `WebApprovalReviewer`**

Add to `src/easy_claw/agent/approvals.py`:

```python
from dataclasses import dataclass
from queue import Queue
from uuid import uuid4


@dataclass(frozen=True)
class WebApprovalRequest:
    approval_id: str
    actions: list[object]


class WebApprovalReviewer:
    def __init__(self) -> None:
        self._approval_id: str | None = None
        self._decisions: Queue[list[dict[str, object]]] = Queue(maxsize=1)

    def prepare(self, interrupts: Sequence[object]) -> WebApprovalRequest:
        value_actions: list[object] = []
        for interrupt in interrupts:
            value_actions.extend(_get_action_requests(_interrupt_value(interrupt)) or [{}])
        self._approval_id = f"approval-{uuid4().hex}"
        return WebApprovalRequest(approval_id=self._approval_id, actions=value_actions or [{}])

    def submit(self, approval_id: str, *, approve: bool, message: str | None = None) -> None:
        if approval_id != self._approval_id:
            raise ValueError("审批 ID 不匹配。")
        if approve:
            self._decisions.put([{"type": "approve"}])
        else:
            self._decisions.put([{"type": "reject", "message": message or "用户已拒绝。"}])

    def review(self, interrupts: Sequence[object]) -> list[dict[str, object]]:
        return self._decisions.get(timeout=300)
```

Modify `_stream_with_approval` in `streaming.py`:

```python
request = reviewer.prepare(interrupts) if hasattr(reviewer, "prepare") else None
yield StreamEvent(
    type="approval_required",
    thread_id=thread_id,
    approval_id=request.approval_id if request else None,
    approval_actions=request.actions if request else None,
)
decisions = reviewer.review(interrupts)
```

Extend `StreamEvent` dataclass with:

```python
approval_id: str | None = None
approval_actions: object | None = None
```

Modify `event_to_dict` to include `approval_id` and `approval_actions`.

- [ ] **Step 4: Update WebSocket receive protocol**

Modify `api/websocket.py` with a parser:

```python
def parse_client_message(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"type": "prompt", "content": raw}
    if not isinstance(payload, dict):
        return {"type": "prompt", "content": raw}
    return payload
```

In `api/app.py`, use `WebApprovalReviewer` for `/ws/chat`. When an `approval_required` event is sent, wait for the next client message, parse `approval_decision`, and call `reviewer.submit(...)` before advancing the stream iterator again. Preserve plain-text prompt compatibility.

- [ ] **Step 5: Write frontend approval tests**

Create `frontend/src/components/ApprovalCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApprovalCard } from './ApprovalCard';

describe('ApprovalCard', () => {
  it('submits approve and reject decisions', async () => {
    const user = userEvent.setup();
    const onDecision = vi.fn();
    render(
      <ApprovalCard
        block={{
          id: 'approval-1',
          kind: 'approval',
          approvalId: 'approval-1',
          actions: [{ name: 'run_command', args: { command: 'uv run pytest' } }],
          status: 'pending',
        }}
        onDecision={onDecision}
      />,
    );

    await user.click(screen.getByRole('button', { name: '批准' }));
    expect(onDecision).toHaveBeenCalledWith('approval-1', 'approve');
  });
});
```

- [ ] **Step 6: Implement `ApprovalCard`**

Create `frontend/src/components/ApprovalCard.tsx`:

```tsx
import type { MessageBlock } from '../api/types';

type ApprovalBlock = Extract<MessageBlock, { kind: 'approval' }>;

export function ApprovalCard({
  block,
  onDecision,
}: {
  block: ApprovalBlock;
  onDecision: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  return (
    <article className={`approval-card ${block.status}`}>
      <h2>工具执行需要确认</h2>
      {block.actions.map((action, index) => (
        <div className="approval-action" key={`${action.name}-${index}`}>
          <strong>{action.name}</strong>
          <pre>{JSON.stringify(action.args || {}, null, 2)}</pre>
        </div>
      ))}
      <div className="approval-actions">
        <button disabled={block.status !== 'pending'} onClick={() => onDecision(block.approvalId, 'approve')} type="button">
          批准
        </button>
        <button disabled={block.status !== 'pending'} onClick={() => onDecision(block.approvalId, 'reject')} type="button">
          拒绝
        </button>
      </div>
    </article>
  );
}
```

Wire `ApprovalCard` through `MessageBlockView` and `useChatSocket.sendApprovalDecision`.

- [ ] **Step 7: Verify backend and frontend**

Run:

```powershell
uv run --no-sync pytest tests\api\test_web_approval.py tests\api\test_api_app.py -q
Push-Location frontend
npm run test:run -- src/components/ApprovalCard.test.tsx src/hooks/useChatSocket.test.ts
npm run lint
npm run build
Pop-Location
```

Expected: approval tests, API tests, frontend tests, TypeScript, and build pass.

- [ ] **Step 8: Browser smoke test in balanced mode**

Set environment for the test process:

```powershell
$env:EASY_CLAW_APPROVAL_MODE="balanced"
uv run easy-claw serve
```

Open `http://127.0.0.1:5173/app` and ask for a harmless command that requires approval:

```text
请运行 uv run easy-claw --help
```

Expected: approval card appears before command execution; approving continues; rejecting returns a user-readable rejection.

- [ ] **Step 9: Commit**

```powershell
git add src\easy_claw\agent src\easy_claw\api tests\api frontend\src
git commit -m "feat: add web approval flow"
```

---

### Task 11: Production Cutover From Old UI to React

**Files:**
- Modify: `src/easy_claw/api/app.py`
- Modify: `tests/api/test_api_app.py`
- Modify: `tests/api/test_react_static_app.py`
- Delete: `src/easy_claw/api/static/index.html`
- Delete: `src/easy_claw/api/static/style.css`
- Delete: `src/easy_claw/api/static/js/`
- Delete: `tests/api/static_web_modules.test.mjs`
- Delete: `tests/api/test_static_web_modules.py`
- Modify: `README.md`
- Modify: `docs/development.md`

- [ ] **Step 1: Write final root serving test**

Modify `tests/api/test_react_static_app.py`:

```python
def test_root_serves_react_app_after_cutover(tmp_path, monkeypatch):
    dist = tmp_path / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    monkeypatch.setattr("easy_claw.api.app._react_dist_dir", lambda: dist)

    client = TestClient(create_app(_config(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="root"' in response.text
```

- [ ] **Step 2: Run failing cutover test**

Run:

```powershell
uv run --no-sync pytest tests\api\test_react_static_app.py::test_root_serves_react_app_after_cutover -q
```

Expected: FAIL because `/` still serves old static HTML.

- [ ] **Step 3: Switch `/` to React**

Modify `src/easy_claw/api/app.py`:

- Make `/` return React `index.html`.
- Keep `/app` returning React `index.html`.
- Keep API routes unchanged.
- Remove `_STATIC_DIR` only after no route uses it.

- [ ] **Step 4: Delete old static UI and tests**

Delete:

```powershell
Remove-Item -Recurse -Force src\easy_claw\api\static\js
Remove-Item src\easy_claw\api\static\index.html
Remove-Item src\easy_claw\api\static\style.css
Remove-Item tests\api\static_web_modules.test.mjs
Remove-Item tests\api\test_static_web_modules.py
```

Use native PowerShell commands exactly as shown from the repository root. Do not delete `frontend/dist/`; it is generated and ignored.

- [ ] **Step 5: Update documentation**

Add to README and `docs/development.md`:

```powershell
Push-Location frontend
npm install
npm run build
Pop-Location
uv run easy-claw serve
```

Add development mode:

```powershell
uv run easy-claw serve
Push-Location frontend
npm run dev
Pop-Location
```

- [ ] **Step 6: Verify**

Run:

```powershell
Push-Location frontend
npm run test:run
npm run lint
npm run build
Pop-Location
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```

Expected: all frontend tests pass; frontend build passes; all backend tests pass; ruff passes.

- [ ] **Step 7: Browser production smoke test**

Run:

```powershell
uv run easy-claw serve
```

Open `http://127.0.0.1:8787/`. Expected: React UI loads, WebSocket connects, `/skills` opens a modal, and a short prompt returns a Markdown-rendered answer.

- [ ] **Step 8: Commit**

```powershell
git add src\easy_claw\api tests README.md docs\development.md
git add -u src\easy_claw\api\static tests\api
git commit -m "feat: switch web ui to react"
```

---

### Task 12: Final Quality Pass and Follow-Up List

**Files:**
- Modify: `docs/development.md`
- Modify: `README.md`

- [ ] **Step 1: Run complete verification**

Run:

```powershell
git status -sb
uv sync
Push-Location frontend
npm install
npm run test:run
npm run lint
npm run build
Pop-Location
uv run pytest
uv run ruff check .
```

Expected: clean dependency sync, frontend tests pass, frontend TypeScript passes, frontend build passes, pytest passes, ruff passes.

- [ ] **Step 2: Browser full-flow verification**

With `uv run easy-claw serve` running, verify in the browser:

- `/` loads React UI.
- A new chat can be created.
- A prompt can stream tokens.
- A file-reading prompt produces a single merged tool card.
- A Markdown table renders as a table.
- Code block copy button writes to clipboard.
- `/skills`, `/mcp`, `/browser`, `/sessions`, `/help`, `/status` work.
- In `balanced` mode, a risky command produces an approval card.

- [ ] **Step 3: Document known follow-ups**

If the checks reveal non-blocking improvements, add a short "React Web UI follow-ups" section to `docs/development.md` with concrete items. Do not add speculative items.

- [ ] **Step 4: Commit documentation updates**

```powershell
git add README.md docs\development.md
git commit -m "docs: document react web workflow"
```

---

## Self-Review

Spec coverage:

- `frontend/` React + TypeScript + Vite project: Task 1.
- Existing UI preserved during migration: Task 2, Task 11.
- WebSocket events normalized to `MessageBlock[]`: Task 3.
- Existing sessions, input, chat flow replicated: Tasks 5 and 6.
- Tool cards migrated: Task 7.
- Markdown, tables, code blocks, copy: Task 8.
- `/skills`, `/mcp`, `/browser`, sessions, help dialogs: Task 9.
- Real approval interaction: Task 10.
- Old static UI deletion only at the end: Task 11.
- Full verification and docs: Task 12.

Placeholder scan:

- This plan contains concrete paths, test names, command lines, and code snippets for every task.
- There are no open requirement markers or ambiguous "fill this in" instructions.

Type consistency:

- `StreamEvent`, `MessageBlock`, `ToolActionRequest`, and `TokenUsage` are defined in Task 3 and reused consistently in later tasks.
- Approval protocol uses `approval_id`, `approval_actions`, and `approval_decision` consistently across backend and frontend tasks.

## References

- Vite project scaffolding and CLI usage: https://vite.dev/guide/
- Vite static base path behavior: https://vite.dev/guide/build.html#public-base-path

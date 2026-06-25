# Runbook Cockpit Frontend Design

Date: 2026-06-25
Project: easy-claw React web UI
Status: Approved design for implementation planning

## Goal

Redesign the easy-claw web frontend from a conventional chat page into a high-density local agent task console. The page should feel like a runbook cockpit for directing a local Windows-first AI agent: users give a goal, watch execution, inspect tool events, approve risky actions, and read the result.

This design supports future multi-theme work by introducing semantic design tokens now, but it does not add a theme switcher or persist theme preferences in this iteration.

## Product Direction

The chosen direction is **Runbook Cockpit**.

The interface should prioritize task execution over casual conversation. It should make the execution trace legible: user task, assistant reasoning/result, tool calls, approval gates, errors, and status context. It should retain the existing backend, WebSocket, session model, and slash-command behavior.

The visual identity is **Obsidian Runbook**: a dark local-control surface inspired by Windows workstation tools, terminal logs, agent execution traces, and the easy-claw “claw” metaphor.

## Visual Identity

### Palette

Use semantic CSS variables rather than hard-coded component colors. The default theme uses these roles:

```css
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
```

Color meaning is role-based:

- user task: yellow
- agent execution and assistant output: blue
- tools, commands, and capabilities: purple
- approval and risky actions: red
- success: green
- warnings: amber

### Typography

Do not add external font dependencies. Use stable local/system fonts:

```css
--font-ui: "Segoe UI Variable", "Microsoft YaHei UI", system-ui, sans-serif;
--font-mono: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
```

Use the UI font for navigation, labels, and prose. Use the mono font for IDs, command names, file paths, tool arguments, code, timing, and compact metadata.

### Signature Element: Claw Rail

The memorable element is a vertical **Claw Rail** in the execution stream. Message blocks, tool events, approval cards, and errors hang from this rail as task events. Each event kind receives a distinct node color and shape. Running tool events may use a subtle pulse animation, disabled by `prefers-reduced-motion: reduce`.

The rail is not decorative. It encodes the execution sequence and makes a long agent run easier to scan.

## Layout

The redesigned page has four regions plus a command dock.

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Status Strip                                              │
│ session · workspace · model · connection · quick commands     │
├───────────────┬────────────────────────────────────┬─────────┤
│ Runbook Nav   │ Execution Stream                   │ Inspector│
│ sessions      │ Claw Rail                          │ current │
│ new task      │ task/tool/approval/result events    │ run     │
├───────────────┴────────────────────────────────────┴─────────┤
│ Command Dock: natural-language prompt + slash hints + execute │
└──────────────────────────────────────────────────────────────┘
```

### Top Status Strip

A narrow read-only strip that answers what context the local agent is running in:

- active session short ID
- workspace path
- model
- connection/status text
- quick command hints such as `/doctor`, `/mcp`, `/skills`

It should be visually quiet and should not compete with the execution stream.

### Runbook Nav

The left navigation remains session-based but adopts task-run language:

- brand: `Easy Claw`
- subtitle: `Local Agent Runbook`
- primary action: `新建任务`
- session rows styled as task records
- short session IDs in mono
- delete buttons visually quiet until hover/focus

The underlying session data model remains unchanged.

### Execution Stream

The center column is the primary surface. It contains the Claw Rail and all message blocks.

The empty state should guide task-oriented use instead of merely saying a session is empty. It should invite the user to give the local agent a goal and show concrete examples such as summarizing a file, checking project structure, running tests, or reading documents.

### Inspector Panel

The right panel is a lightweight contextual inspector, not a new dashboard. In this iteration it can show:

- active session ID
- model
- workspace
- connection/status text
- notice or error text
- common slash-command hints

It should not trigger new network requests. It prepares a stable area for future theme switching and capability status without adding those features now.

### Command Dock

The input area becomes a bottom command dock:

- placeholder: `描述任务，或输入 /doctor、/mcp、/skills`
- submit button text: `执行`
- disabled state clearly communicates that the agent is running
- Enter submits as today
- slash command hints remain visible but secondary

## Component Plan

### AppShell

Expand `AppShell` from a two-column shell into a layout skeleton that accepts:

- `topbar`
- `sidebar`
- `inspector`
- `children` for the execution area

Keep semantic `main` structure and accessible labels.

### App

Keep API/WebSocket behavior unchanged. Compose the new shell regions from existing state:

- sessions
- active session
- load error
- notice
- web config
- chat status and blocks

No new backend endpoint is required.

### Sidebar

Keep the existing component name unless renaming is clearly simpler during implementation. Update copy and markup to support runbook navigation:

- `Local Agent` becomes `Local Agent Runbook`
- `新建会话` becomes `新建任务`
- rows become denser task records
- IDs use mono styling

### StatusStrip

Add a small presentational component for the top strip. It receives already-known state and renders compact metadata. It should not fetch data.

### InspectorPanel

Add a presentational component for contextual metadata and hints. It receives already-known state and renders compact cards or rows. It should not fetch data.

### ChatView and MessageBlockView

Wrap each message block as a rail event with classes based on block kind and status. Preserve the existing message rendering and message data types.

Update the empty state to a task-console welcome panel.

### ToolCard

Restyle as a run event card:

- tool name and status in header
- duration and completion state as compact metadata
- argument summary as trace text
- expandable arguments and result remain
- copy result remains
- running/done/error states map to semantic tokens

### ApprovalCard

Restyle as a risk gate:

- red/risk accent
- action content remains readable
- approve/reject buttons are clear and keyboard-focusable

### ChatInput

Restyle as the command dock and change submit copy from `发送` to `执行`. Keep current form behavior and Enter submission.

## Interaction and Accessibility

- Use hover only for interactive elements.
- Provide strong `:focus-visible` styles for buttons, inputs, and expandable controls.
- Keep tool outputs collapsed by default to preserve high-density scanability.
- Respect `prefers-reduced-motion: reduce`.
- Ensure mobile and narrow widths remain usable.
- Preserve existing aria labels or replace them with equally clear Chinese labels.

## Responsive Behavior

Desktop:

- top status strip
- left runbook nav
- center execution stream
- right inspector
- bottom command dock

Tablet:

- left nav narrows
- inspector moves above or below the execution stream as a compact summary

Mobile:

- single column
- navigation becomes a compact top block
- inspector is hidden or rendered as a compact summary
- Claw Rail remains but with smaller nodes and reduced indentation

## Testing and Verification

Update tests affected by copy or structure changes, especially:

- `frontend/src/components/Sidebar.test.tsx`
- `frontend/src/components/ChatInput.test.tsx`
- `frontend/src/components/ToolCard.test.tsx`
- `frontend/src/App.test.tsx`
- `frontend/src/styles.test.ts`

Add or adjust assertions for:

- new runbook copy
- command dock submit copy
- status/inspector rendering
- style token presence
- responsive/reduced-motion CSS where existing style tests make this practical

Run at minimum:

```powershell
Push-Location frontend
npm test -- --run
npm run build
Pop-Location
```

If dependencies are not installed, run `npm install` or report that verification was blocked by missing dependencies.

## Scope Boundaries

This design includes:

- tokenized visual system
- Runbook Cockpit layout
- Claw Rail execution stream
- component restyling for navigation, input, tools, approvals, markdown, modal surfaces
- test updates for changed copy/structure

This design excludes:

- theme switching UI
- persisted theme preferences
- new backend APIs
- new WebSocket message types
- backend session model changes
- dashboard charts
- new external font or icon dependencies

## Acceptance Criteria

- The first impression is a local agent task console, not a generic chat app.
- Execution events are easier to scan than in the current UI.
- User tasks, assistant output, tool calls, approvals, and errors have distinct visual roles.
- CSS variables make future themes straightforward.
- Desktop, tablet, and mobile layouts remain usable.
- Keyboard focus is visible.
- Reduced-motion users do not receive unnecessary animation.
- Updated frontend tests pass.

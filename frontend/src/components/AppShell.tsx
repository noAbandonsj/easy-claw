import type { ReactNode } from 'react';

export function AppShell({ children, sidebar }: { children: ReactNode; sidebar: ReactNode }) {
  return (
    <main className="app-shell">
      {sidebar}
      <section className="chat-pane" aria-label="聊天工作区">
        {children}
      </section>
    </main>
  );
}

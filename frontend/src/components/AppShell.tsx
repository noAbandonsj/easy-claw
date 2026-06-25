import type { ReactNode } from 'react';

type AppShellProps = {
  children: ReactNode;
  inspector: ReactNode;
  sidebar: ReactNode;
  topbar: ReactNode;
};

export function AppShell({ children, inspector, sidebar, topbar }: AppShellProps) {
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

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

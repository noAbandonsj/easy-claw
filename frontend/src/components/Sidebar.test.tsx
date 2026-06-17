import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Sidebar } from './Sidebar';

describe('Sidebar', () => {
  it('renders sessions and the active status', () => {
    render(
      <Sidebar
        activeSessionId="session-1"
        onNewSession={vi.fn()}
        onSelectSession={vi.fn()}
        sessions={[
          {
            id: 'session-1',
            title: '网页聊天',
            workspace_path: 'D:/workspace',
            model: 'deepseek-v4-pro',
            created_at: '2026-06-17T00:00:00+00:00',
            updated_at: '2026-06-17T00:00:00+00:00',
          },
        ]}
        status="就绪"
      />,
    );

    expect(screen.getByRole('heading', { name: 'Easy Claw' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '新建会话' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /网页聊天/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
    expect(screen.getByLabelText('连接状态')).toHaveTextContent('就绪');
  });
});

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

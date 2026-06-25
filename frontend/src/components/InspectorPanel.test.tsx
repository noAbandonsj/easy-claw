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

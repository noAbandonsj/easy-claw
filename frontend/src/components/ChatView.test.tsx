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

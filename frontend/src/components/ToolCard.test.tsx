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

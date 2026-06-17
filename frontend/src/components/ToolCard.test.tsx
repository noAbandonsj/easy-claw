import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ToolCard } from './ToolCard';

describe('ToolCard', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders a merged tool call and result card', () => {
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

    expect(screen.getByRole('heading', { name: 'read_file' })).toBeInTheDocument();
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.getByText(/README.md/)).toBeInTheDocument();
    expect(screen.getByText(/easy-claw/)).toBeInTheDocument();
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
});

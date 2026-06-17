import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApprovalCard } from './ApprovalCard';

describe('ApprovalCard', () => {
  it('submits approve and reject decisions', () => {
    const onDecision = vi.fn();
    render(
      <ApprovalCard
        block={{
          id: 'approval-1',
          kind: 'approval',
          approvalId: 'approval-1',
          actions: [{ name: 'run_command', args: { command: 'uv run pytest' } }],
          status: 'pending',
        }}
        onDecision={onDecision}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '批准' }));
    expect(onDecision).toHaveBeenCalledWith('approval-1', 'approve');

    fireEvent.click(screen.getByRole('button', { name: '拒绝' }));
    expect(onDecision).toHaveBeenCalledWith('approval-1', 'reject');
  });
});

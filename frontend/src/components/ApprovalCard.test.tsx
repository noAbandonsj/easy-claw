import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApprovalCard } from './ApprovalCard';

const block = {
  id: 'approval-1',
  kind: 'approval' as const,
  approvalId: 'approval-1',
  actions: [{ name: 'run_command', args: { command: 'Remove-Item file.txt' } }],
  status: 'pending' as const,
};

describe('ApprovalCard', () => {
  it('renders a risk gate with action details', () => {
    render(<ApprovalCard block={block} onDecision={vi.fn()} />);

    expect(screen.getByRole('article', { name: '风险审批 run_command' })).toHaveClass('risk-gate');
    expect(screen.getByRole('heading', { name: '风险操作需要确认' })).toBeInTheDocument();
    expect(screen.getByText('待确认')).toBeInTheDocument();
    expect(screen.getByText('run_command')).toBeInTheDocument();
    expect(screen.getByText(/Remove-Item file.txt/)).toBeInTheDocument();
  });

  it('sends approve and reject decisions while pending', () => {
    const onDecision = vi.fn();
    render(<ApprovalCard block={block} onDecision={onDecision} />);

    fireEvent.click(screen.getByRole('button', { name: '批准执行' }));
    fireEvent.click(screen.getByRole('button', { name: '拒绝执行' }));

    expect(onDecision).toHaveBeenNthCalledWith(1, 'approval-1', 'approve');
    expect(onDecision).toHaveBeenNthCalledWith(2, 'approval-1', 'reject');
  });

  it('disables decisions after the approval is resolved', () => {
    render(<ApprovalCard block={{ ...block, status: 'approved' }} onDecision={vi.fn()} />);

    expect(screen.getByText('已批准')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '批准执行' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '拒绝执行' })).toBeDisabled();
  });
});

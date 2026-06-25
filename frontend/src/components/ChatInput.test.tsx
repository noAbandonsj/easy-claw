import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatInput } from './ChatInput';

describe('ChatInput', () => {
  it('submits non-empty tasks and clears the field', () => {
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('消息'), { target: { value: '总结 README' } });
    fireEvent.click(screen.getByRole('button', { name: '执行' }));

    expect(onSubmit).toHaveBeenCalledWith('总结 README');
    expect(screen.getByLabelText('消息')).toHaveValue('');
  });

  it('submits with Enter and clears the field', () => {
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('消息'), { target: { value: '/status' } });
    fireEvent.keyDown(screen.getByLabelText('消息'), { key: 'Enter' });

    expect(onSubmit).toHaveBeenCalledWith('/status');
    expect(screen.getByLabelText('消息')).toHaveValue('');
  });

  it('does not submit with Enter after becoming disabled', () => {
    const onSubmit = vi.fn();
    const { rerender } = render(<ChatInput disabled={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('消息'), { target: { value: '/status' } });
    rerender(<ChatInput disabled={true} onSubmit={onSubmit} />);
    fireEvent.keyDown(screen.getByLabelText('消息'), { key: 'Enter' });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('shows a command dock hint and disables execution while unavailable', () => {
    render(<ChatInput disabled={true} onSubmit={vi.fn()} />);

    expect(screen.getByText('自然语言任务或 slash command')).toBeInTheDocument();
    expect(screen.getByText('/doctor')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '执行' })).toBeDisabled();
  });
});

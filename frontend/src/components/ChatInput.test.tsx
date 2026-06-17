import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatInput } from './ChatInput';

describe('ChatInput', () => {
  it('submits non-empty messages and clears the field', () => {
    const onSubmit = vi.fn();
    render(<ChatInput disabled={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('消息'), { target: { value: '总结 README' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    expect(onSubmit).toHaveBeenCalledWith('总结 README');
    expect(screen.getByLabelText('消息')).toHaveValue('');
  });
});

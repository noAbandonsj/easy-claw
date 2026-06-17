import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CodeBlock } from './CodeBlock';

describe('CodeBlock', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('copies code content', () => {
    const writeText = vi.fn();
    vi.stubGlobal('navigator', { clipboard: { writeText } });

    render(<CodeBlock language="powershell" value="uv run easy-claw serve" />);

    fireEvent.click(screen.getByRole('button', { name: '复制代码' }));

    expect(writeText).toHaveBeenCalledWith('uv run easy-claw serve');
  });
});

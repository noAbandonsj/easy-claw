import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarkdownMessage } from './MarkdownMessage';

describe('MarkdownMessage', () => {
  it('renders GFM headings, tables, and code blocks', () => {
    render(
      <MarkdownMessage
        content={
          '## 结果\n\n| 名称 | 状态 | 备注 |\n| --- | --- | --- |\n| easy-claw | 通过 | ok |\n\n```powershell\nuv run easy-claw serve\n```'
        }
        streaming={false}
      />,
    );

    expect(screen.getByRole('heading', { name: '结果' })).toBeInTheDocument();
    const table = screen.getByRole('table');
    expect(within(table).getByText('easy-claw')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '复制代码' })).toBeInTheDocument();
    expect(screen.getByText('uv run easy-claw serve')).toBeInTheDocument();
  });
});

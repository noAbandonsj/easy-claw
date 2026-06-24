import { describe, expect, it } from 'vitest';
import type { MessageBlock } from '../api/types';
import { reduceStreamEvent } from './messageBlocks';

describe('reduceStreamEvent', () => {
  it('appends assistant text tokens into one assistant block', () => {
    let blocks: MessageBlock[] = [];
    blocks = reduceStreamEvent(blocks, { type: 'token', content: '## 标题' });
    blocks = reduceStreamEvent(blocks, { type: 'token', content: '\n内容' });

    expect(blocks).toEqual([
      {
        id: 'assistant-1',
        kind: 'assistant',
        content: '## 标题\n内容',
        streaming: true,
      },
    ]);
  });

  it('marks the assistant block complete when done arrives', () => {
    let blocks: MessageBlock[] = [];
    blocks = reduceStreamEvent(blocks, { type: 'token', content: '完成' });
    blocks = reduceStreamEvent(blocks, { type: 'done' });

    expect(blocks).toEqual([
      {
        id: 'assistant-1',
        kind: 'assistant',
        content: '完成',
        streaming: false,
      },
    ]);
  });

  it('merges tool result into the matching pending tool block', () => {
    let blocks: MessageBlock[] = [];
    blocks = reduceStreamEvent(blocks, {
      type: 'tool_call_start',
      tool_name: 'read_file',
      tool_args: { path: 'README.md' },
    });
    blocks = reduceStreamEvent(blocks, {
      type: 'tool_call_result',
      tool_name: 'read_file',
      tool_result: '# easy-claw',
    });

    expect(blocks).toEqual([
      {
        id: 'tool-1',
        kind: 'tool',
        name: 'read_file',
        args: { path: 'README.md' },
        result: '# easy-claw',
        status: 'finished',
      },
    ]);
  });

  it('keeps local tool timing metadata when merging tool results', () => {
    let blocks: MessageBlock[] = [];
    blocks = reduceStreamEvent(blocks, {
      type: 'tool_call_start',
      tool_name: 'read_file',
      tool_args: { path: 'README.md' },
      startedAt: 1000,
    });
    blocks = reduceStreamEvent(blocks, {
      type: 'tool_call_result',
      tool_name: 'read_file',
      tool_result: '# easy-claw',
      finishedAt: 2450,
    });

    expect(blocks).toEqual([
      {
        id: 'tool-1',
        kind: 'tool',
        name: 'read_file',
        args: { path: 'README.md' },
        result: '# easy-claw',
        status: 'finished',
        startedAt: 1000,
        finishedAt: 2450,
      },
    ]);
  });

  it('adds approval blocks from approval_required events', () => {
    const blocks = reduceStreamEvent([], {
      type: 'approval_required',
      approval_id: 'approval-1',
      approval_actions: [{ name: 'run_command', args: { command: 'uv run pytest' } }],
    });

    expect(blocks).toEqual([
      {
        id: 'approval-1',
        kind: 'approval',
        approvalId: 'approval-1',
        actions: [{ name: 'run_command', args: { command: 'uv run pytest' } }],
        status: 'pending',
      },
    ]);
  });
});

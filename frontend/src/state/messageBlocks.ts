import type { MessageBlock, StreamEvent, ToolActionRequest } from '../api/types';

function nextBlockId(blocks: MessageBlock[], kind: MessageBlock['kind']): string {
  return `${kind}-${blocks.filter(block => block.kind === kind).length + 1}`;
}

function isAssistantBlock(
  block: MessageBlock | undefined,
): block is Extract<MessageBlock, { kind: 'assistant' }> {
  return block?.kind === 'assistant';
}

function isToolBlock(
  block: MessageBlock,
): block is Extract<MessageBlock, { kind: 'tool' }> {
  return block.kind === 'tool';
}

function normalizeToolActions(actions: ToolActionRequest[] | undefined): ToolActionRequest[] {
  return actions?.length ? actions : [{ name: 'unknown' }];
}

export function userMessageBlock(content: string, blocks: MessageBlock[]): MessageBlock {
  return {
    id: nextBlockId(blocks, 'user'),
    kind: 'user',
    content,
  };
}

export function markApprovalDecision(
  blocks: MessageBlock[],
  approvalId: string,
  decision: 'approve' | 'reject',
): MessageBlock[] {
  return blocks.map(block => {
    if (block.kind !== 'approval' || block.approvalId !== approvalId) {
      return block;
    }
    return {
      ...block,
      status: decision === 'approve' ? 'approved' : 'rejected',
    };
  });
}

export function reduceStreamEvent(blocks: MessageBlock[], event: StreamEvent): MessageBlock[] {
  switch (event.type) {
    case 'token': {
      const lastBlock = blocks.at(-1);
      if (isAssistantBlock(lastBlock) && lastBlock.streaming) {
        return [
          ...blocks.slice(0, -1),
          {
            ...lastBlock,
            content: lastBlock.content + event.content,
          },
        ];
      }
      return [
        ...blocks,
        {
          id: nextBlockId(blocks, 'assistant'),
          kind: 'assistant',
          content: event.content,
          streaming: true,
        },
      ];
    }
    case 'tool_call_start':
      return [
        ...blocks,
        {
          id: nextBlockId(blocks, 'tool'),
          kind: 'tool',
          name: event.tool_name || 'unknown_tool',
          args: event.tool_args ?? {},
          result: undefined,
          status: 'running',
        },
      ];
    case 'tool_call_result': {
      let index = -1;
      for (let blockIndex = blocks.length - 1; blockIndex >= 0; blockIndex -= 1) {
        const block = blocks[blockIndex];
        if (
          isToolBlock(block) &&
          block.status === 'running' &&
          block.name === (event.tool_name || block.name)
        ) {
          index = blockIndex;
          break;
        }
      }
      if (index === -1) {
        return [
          ...blocks,
          {
            id: nextBlockId(blocks, 'tool'),
            kind: 'tool',
            name: event.tool_name || 'unknown_tool',
            args: {},
            result: event.tool_result ?? event.content ?? '',
            status: 'finished',
          },
        ];
      }
      return blocks.map((block, blockIndex) =>
        blockIndex === index && isToolBlock(block)
          ? {
              ...block,
              result: event.tool_result ?? event.content ?? '',
              status: 'finished',
            }
          : block,
      );
    }
    case 'approval_required':
      return [
        ...blocks,
        {
          id: event.approval_id || nextBlockId(blocks, 'approval'),
          kind: 'approval',
          approvalId: event.approval_id || nextBlockId(blocks, 'approval'),
          actions: normalizeToolActions(event.approval_actions),
          status: 'pending',
        },
      ];
    case 'done':
      return blocks.map(block =>
        block.kind === 'assistant'
          ? {
              ...block,
              streaming: false,
            }
          : block,
      );
    case 'error':
      return [
        ...blocks,
        {
          id: nextBlockId(blocks, 'error'),
          kind: 'error',
          content: event.content || '发生错误',
        },
      ];
    case 'interrupted':
      return [
        ...blocks,
        {
          id: nextBlockId(blocks, 'error'),
          kind: 'error',
          content: event.content || '执行已中断',
        },
      ];
    case 'banner':
      return blocks;
    default:
      return blocks;
  }
}

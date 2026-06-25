import type { MessageBlock } from '../api/types';
import { ApprovalCard } from './ApprovalCard';
import { MarkdownMessage } from './MarkdownMessage';
import { ToolCard } from './ToolCard';

function railClass(block: MessageBlock): string {
  const status = 'status' in block ? ` rail-event-${block.status}` : '';
  return `rail-event rail-event-${block.kind}${status}`;
}

export function MessageBlockView({
  block,
  onApprovalDecision,
}: {
  block: MessageBlock;
  onApprovalDecision?: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  let content;

  if (block.kind === 'user') {
    content = (
      <article className="message user-message">
        <span className="message-label">你</span>
        <p>{block.content}</p>
      </article>
    );
  } else if (block.kind === 'assistant') {
    content = <MarkdownMessage content={block.content} streaming={block.streaming} />;
  } else if (block.kind === 'tool') {
    content = <ToolCard block={block} />;
  } else if (block.kind === 'approval') {
    content = (
      <ApprovalCard block={block} onDecision={onApprovalDecision || (() => undefined)} />
    );
  } else {
    content = (
      <article className="message error-message">
        <span className="message-label">错误</span>
        <p>{block.content}</p>
      </article>
    );
  }

  return <div className={railClass(block)}>{content}</div>;
}

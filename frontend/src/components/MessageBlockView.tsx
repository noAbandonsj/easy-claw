import type { MessageBlock } from '../api/types';
import { ApprovalCard } from './ApprovalCard';
import { MarkdownMessage } from './MarkdownMessage';
import { ToolCard } from './ToolCard';

export function MessageBlockView({
  block,
  onApprovalDecision,
}: {
  block: MessageBlock;
  onApprovalDecision?: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  if (block.kind === 'user') {
    return (
      <article className="message user-message">
        <span className="message-label">你</span>
        <p>{block.content}</p>
      </article>
    );
  }

  if (block.kind === 'assistant') {
    return <MarkdownMessage content={block.content} streaming={block.streaming} />;
  }

  if (block.kind === 'tool') {
    return <ToolCard block={block} />;
  }

  if (block.kind === 'approval') {
    return (
      <ApprovalCard
        block={block}
        onDecision={onApprovalDecision || (() => undefined)}
      />
    );
  }

  return (
    <article className="message error-message">
      <span className="message-label">错误</span>
      <p>{block.content}</p>
    </article>
  );
}

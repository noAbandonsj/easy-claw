import type { MessageBlock } from '../api/types';
import { MarkdownMessage } from './MarkdownMessage';
import { ToolCard } from './ToolCard';

export function MessageBlockView({ block }: { block: MessageBlock }) {
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
      <article className={`approval-card ${block.status}`}>
        <h2>工具执行需要确认</h2>
        <p>{block.status === 'pending' ? '等待处理' : block.status}</p>
      </article>
    );
  }

  return (
    <article className="message error-message">
      <span className="message-label">错误</span>
      <p>{block.content}</p>
    </article>
  );
}

import type { MessageBlock } from '../api/types';

function formatUnknown(value: unknown): string {
  if (value === undefined || value === null || value === '') {
    return '';
  }
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

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
    return (
      <article className="message assistant-message">
        <span className="message-label">Easy Claw</span>
        <p>{block.content}</p>
        {block.streaming ? <span className="cursor" /> : null}
      </article>
    );
  }

  if (block.kind === 'tool') {
    return (
      <article className={`tool-panel ${block.status}`}>
        <div className="tool-summary">
          <strong>{block.name}</strong>
          <span>{block.status === 'running' ? '执行中' : '已完成'}</span>
        </div>
        <pre>{formatUnknown(block.result || block.args)}</pre>
      </article>
    );
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

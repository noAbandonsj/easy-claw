import type { MessageBlock } from '../api/types';

type ToolBlock = Extract<MessageBlock, { kind: 'tool' }>;

function formatUnknown(value: unknown): string {
  if (value === undefined || value === null || value === '') {
    return '';
  }
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

export function ToolCard({ block }: { block: ToolBlock }) {
  const result = formatUnknown(block.result);
  const args = formatUnknown(block.args);

  function copyResult() {
    void navigator.clipboard?.writeText(result);
  }

  return (
    <article className={`tool-panel ${block.status}`}>
      <div className="tool-summary">
        <div>
          <span className="message-label">工具调用</span>
          <h2>{block.name}</h2>
        </div>
        <span>{block.status === 'running' ? '执行中' : '已完成'}</span>
      </div>
      {args ? (
        <div className="tool-section">
          <strong>参数</strong>
          <pre>{args}</pre>
        </div>
      ) : null}
      {result ? (
        <div className="tool-section">
          <div className="tool-section-header">
            <strong>结果</strong>
            <button onClick={copyResult} type="button">
              复制结果
            </button>
          </div>
          <pre>{result}</pre>
        </div>
      ) : null}
    </article>
  );
}

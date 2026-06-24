import type { MessageBlock } from '../api/types';
import { useState } from 'react';

type ToolBlock = Extract<MessageBlock, { kind: 'tool' }>;

function formatUnknown(value: unknown): string {
  if (value === undefined || value === null || value === '') {
    return '';
  }
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function isEmptyObject(value: unknown): boolean {
  return (
    value !== null &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.keys(value).length === 0
  );
}

function compactText(value: string, maxLength = 120): string {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

function summarizeArgs(args: unknown, status: ToolBlock['status']): string {
  if (args === undefined || args === null || args === '' || isEmptyObject(args)) {
    return status === 'running' ? '正在解析参数...' : '未提供参数';
  }

  if (typeof args === 'string') {
    return compactText(args);
  }

  if (typeof args === 'object' && !Array.isArray(args)) {
    const values = args as Record<string, unknown>;
    for (const key of ['path', 'file_path', 'file', 'command', 'query', 'url', 'pattern']) {
      const value = values[key];
      if (value !== undefined && value !== null && value !== '') {
        return compactText(String(value));
      }
    }
  }

  return compactText(formatUnknown(args).replace(/\s+/g, ' '));
}

function formatDuration(startedAt: number | undefined, finishedAt: number | undefined): string {
  if (startedAt === undefined || finishedAt === undefined || finishedAt < startedAt) {
    return '';
  }
  const elapsedMs = finishedAt - startedAt;
  if (elapsedMs < 1000) {
    return `${elapsedMs}ms`;
  }
  return `${(Math.round(elapsedMs / 100) / 10).toFixed(1)}s`;
}

function formatSize(value: string): string {
  if (value.length < 1024) {
    return `${value.length} B`;
  }
  return `${(value.length / 1024).toFixed(1)} KB`;
}

export function ToolCard({ block }: { block: ToolBlock }) {
  const [argsOpen, setArgsOpen] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);
  const result = formatUnknown(block.result);
  const args = formatUnknown(block.args);
  const argSummary = summarizeArgs(block.args, block.status);
  const duration = formatDuration(block.startedAt, block.finishedAt);
  const hasArgsDetails =
    block.args !== undefined && block.args !== null && block.args !== '' && !isEmptyObject(block.args);

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
        <div className="tool-meta">
          {duration ? <span>{duration}</span> : null}
          <span>{block.status === 'running' ? '执行中' : '已完成'}</span>
        </div>
      </div>
      <div className="tool-section">
        <div className="tool-section-header">
          <strong>参数</strong>
          {hasArgsDetails ? (
            <button onClick={() => setArgsOpen(current => !current)} type="button">
              {argsOpen ? '收起参数' : '查看参数'}
            </button>
          ) : null}
        </div>
        <p className="tool-argument-summary">{argSummary}</p>
        {argsOpen ? <pre>{args}</pre> : null}
      </div>
      {result ? (
        <div className="tool-section">
          <div className="tool-section-header">
            <strong>结果 {formatSize(result)}</strong>
            <div className="tool-actions">
              <button onClick={() => setResultOpen(current => !current)} type="button">
                {resultOpen ? '收起结果' : '展开结果'}
              </button>
              <button onClick={copyResult} type="button">
                复制结果
              </button>
            </div>
          </div>
          {resultOpen ? <pre>{result}</pre> : null}
        </div>
      ) : null}
    </article>
  );
}

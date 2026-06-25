import type { MessageBlock } from '../api/types';
import { MessageBlockView } from './MessageBlockView';

export function ChatView({
  blocks,
  onApprovalDecision,
}: {
  blocks: MessageBlock[];
  onApprovalDecision?: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  return (
    <section className="chat-stream claw-rail" aria-label="任务执行轨迹">
      {blocks.length ? (
        blocks.map(block => (
          <MessageBlockView
            block={block}
            key={block.id}
            onApprovalDecision={onApprovalDecision}
          />
        ))
      ) : (
        <article className="message assistant-message empty-runbook-panel">
          <span className="message-label">Runbook Ready</span>
          <h2>给本地 agent 一个目标</h2>
          <p>描述你要完成的任务，Easy Claw 会把对话、工具调用、审批和结果串成一条执行轨迹。</p>
          <ul className="starter-list">
            <li>总结 README.md</li>
            <li>检查项目结构</li>
            <li>运行测试并解释失败</li>
            <li>读取文件并提炼行动项</li>
          </ul>
        </article>
      )}
    </section>
  );
}

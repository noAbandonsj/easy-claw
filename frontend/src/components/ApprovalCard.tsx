import type { MessageBlock } from '../api/types';

type ApprovalBlock = Extract<MessageBlock, { kind: 'approval' }>;

export function ApprovalCard({
  block,
  onDecision,
}: {
  block: ApprovalBlock;
  onDecision: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  const disabled = block.status !== 'pending';

  return (
    <article className={`approval-card ${block.status}`}>
      <h2>工具执行需要确认</h2>
      {block.actions.map((action, index) => (
        <div className="approval-action" key={`${action.name}-${index}`}>
          <strong>{action.name}</strong>
          <pre>{JSON.stringify(action.args || {}, null, 2)}</pre>
        </div>
      ))}
      <div className="approval-actions">
        <button
          disabled={disabled}
          onClick={() => onDecision(block.approvalId, 'approve')}
          type="button"
        >
          批准
        </button>
        <button
          disabled={disabled}
          onClick={() => onDecision(block.approvalId, 'reject')}
          type="button"
        >
          拒绝
        </button>
      </div>
    </article>
  );
}

import type { MessageBlock } from '../api/types';

type ApprovalBlock = Extract<MessageBlock, { kind: 'approval' }>;

function approvalStatusText(status: ApprovalBlock['status']): string {
  if (status === 'approved') {
    return '已批准';
  }
  if (status === 'rejected') {
    return '已拒绝';
  }
  return '待确认';
}

export function ApprovalCard({
  block,
  onDecision,
}: {
  block: ApprovalBlock;
  onDecision: (approvalId: string, decision: 'approve' | 'reject') => void;
}) {
  const disabled = block.status !== 'pending';
  const primaryAction = block.actions[0]?.name || '未知操作';

  return (
    <article aria-label={`风险审批 ${primaryAction}`} className={`approval-card risk-gate ${block.status}`}>
      <div className="risk-gate-header">
        <div>
          <span className="message-label">Risk Gate</span>
          <h2>风险操作需要确认</h2>
        </div>
        <span className="risk-gate-status">{approvalStatusText(block.status)}</span>
      </div>
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
          批准执行
        </button>
        <button
          disabled={disabled}
          onClick={() => onDecision(block.approvalId, 'reject')}
          type="button"
        >
          拒绝执行
        </button>
      </div>
    </article>
  );
}

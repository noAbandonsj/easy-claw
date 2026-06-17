from __future__ import annotations

from easy_claw.agent.approvals import WebApprovalReviewer
from easy_claw.agent.streaming import StreamEvent
from easy_claw.api.websocket import event_to_dict


def test_web_approval_reviewer_returns_submitted_approval_decision():
    reviewer = WebApprovalReviewer()
    request = reviewer.prepare(
        [{"action_requests": [{"name": "run_command", "args": {"command": "uv run pytest"}}]}]
    )

    assert request.approval_id.startswith("approval-")
    assert request.actions == [{"name": "run_command", "args": {"command": "uv run pytest"}}]

    reviewer.submit(request.approval_id, approve=True)

    assert reviewer.review([]) == [{"type": "approve"}]


def test_web_approval_reviewer_returns_rejection_message():
    reviewer = WebApprovalReviewer()
    request = reviewer.prepare([{"action_requests": [{"name": "run_command", "args": {}}]}])

    reviewer.submit(request.approval_id, approve=False, message="用户拒绝")

    assert reviewer.review([]) == [{"type": "reject", "message": "用户拒绝"}]


def test_approval_stream_event_serializes_action_payload():
    event = StreamEvent(
        type="approval_required",
        approval_id="approval-1",
        approval_actions=[{"name": "run_command", "args": {"command": "uv run pytest"}}],
    )

    assert event_to_dict(event) == {
        "type": "approval_required",
        "approval_id": "approval-1",
        "approval_actions": [
            {"name": "run_command", "args": {"command": "uv run pytest"}},
        ],
    }

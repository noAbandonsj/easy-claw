from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class ApprovalReviewer(Protocol):
    def review(self, interrupts: Sequence[object]) -> list[dict[str, object]]:
        """返回 LangGraph 人工审批决策。"""


class StaticApprovalReviewer:
    def __init__(self, *, approve: bool) -> None:
        self._approve = approve

    def review(self, interrupts: Sequence[object]) -> list[dict[str, object]]:
        decisions: list[dict[str, object]] = []
        for interrupt in interrupts:
            action_count = max(1, len(_get_action_requests(_interrupt_value(interrupt))))
            for _ in range(action_count):
                if self._approve:
                    decisions.append({"type": "approve"})
                else:
                    decisions.append({"type": "reject", "message": "用户已拒绝。"})
        return decisions


class ConsoleApprovalReviewer:
    def review(self, interrupts: Sequence[object]) -> list[dict[str, object]]:
        decisions: list[dict[str, object]] = []
        for interrupt in interrupts:
            value = _interrupt_value(interrupt)
            actions = _get_action_requests(value) or [{}]
            for action in actions:
                name = _read_field(action, "name") or "未知工具"
                args = _read_field(action, "args") or {}
                description = _read_field(action, "description")
                print("\n工具执行需要确认")
                print(f"工具: {name}")
                print(f"参数: {args}")
                if description:
                    print(f"原因: {description}")
                answer = input("允许执行？[y/N] ").strip().lower()
                if answer in {"y", "yes"}:
                    decisions.append({"type": "approve"})
                else:
                    decisions.append({"type": "reject", "message": "用户已拒绝。"})
        return decisions


def _interrupt_value(interrupt: object) -> object:
    return getattr(interrupt, "value", interrupt)


def _get_action_requests(value: object) -> list[object]:
    actions = _read_field(value, "action_requests")
    if actions is None:
        return []
    return list(actions)


def _read_field(value: object, field_name: str) -> object | None:
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)

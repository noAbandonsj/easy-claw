from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
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
                if _read_yes_no_selection("允许执行？", default=True):
                    decisions.append({"type": "approve"})
                else:
                    decisions.append({"type": "reject", "message": "用户已拒绝。"})
        return decisions


def _read_yes_no_selection(
    prompt: str,
    *,
    default: bool = True,
    read_key: Callable[[], str] | None = None,
    write: Callable[[str], object] | None = None,
) -> bool:
    selected = default
    key_reader = read_key or _read_console_selection_key
    writer = write or _write_console_selection

    while True:
        writer("\r" + _format_yes_no_selection(prompt, selected))
        key = key_reader()
        if key == "enter":
            writer("\n")
            return selected
        if key == "confirm_yes":
            writer("\r" + _format_yes_no_selection(prompt, True) + "\n")
            return True
        if key == "confirm_no":
            writer("\r" + _format_yes_no_selection(prompt, False) + "\n")
            return False
        if key in {"left", "yes"}:
            selected = True
        elif key in {"right", "no"}:
            selected = False
        elif key == "tab":
            selected = not selected


def _format_yes_no_selection(prompt: str, selected_yes: bool) -> str:
    yes = "[Yes]" if selected_yes else " Yes "
    no = "[No]" if not selected_yes else " No "
    return f"{prompt} {yes}  {no}"


def _write_console_selection(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _read_console_selection_key() -> str:
    try:
        import msvcrt
    except ImportError:
        answer = input().strip().lower()
        if answer in {"", "y", "yes"}:
            return "confirm_yes"
        if answer in {"n", "no"}:
            return "confirm_no"
        return "enter"

    ch = msvcrt.getch()
    if ch in {b"\r", b"\n"}:
        return "enter"
    if ch == b"\t":
        return "tab"
    if ch in {b"y", b"Y"}:
        return "yes"
    if ch in {b"n", b"N"}:
        return "no"
    if ch == b"\x03":
        raise KeyboardInterrupt
    if ch in {b"\x00", b"\xe0"}:
        second = msvcrt.getch()
        if second == b"K":
            return "left"
        if second == b"M":
            return "right"
    return ""


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

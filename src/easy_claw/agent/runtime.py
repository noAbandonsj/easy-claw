from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentRequest:
    prompt: str
    thread_id: str
    workspace_path: Path
    model: str | None
    base_url: str = "https://api.deepseek.com"
    api_key: str | None = None
    skill_sources: Sequence[str] = field(default_factory=tuple)
    memories: Sequence[str] = field(default_factory=tuple)
    checkpoint_db_path: Path | None = None


@dataclass(frozen=True)
class AgentResult:
    content: str
    thread_id: str


class AgentRuntime(Protocol):
    def run(self, request: AgentRequest) -> AgentResult:
        """Run one agent turn."""


class ApprovalReviewer(Protocol):
    def review(self, interrupts: Sequence[object]) -> list[dict[str, object]]:
        """Return LangGraph HITL decisions for interrupt payloads."""


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
                    decisions.append({"type": "reject", "message": "Rejected by user."})
        return decisions


class ConsoleApprovalReviewer:
    def review(self, interrupts: Sequence[object]) -> list[dict[str, object]]:
        decisions: list[dict[str, object]] = []
        for interrupt in interrupts:
            value = _interrupt_value(interrupt)
            actions = _get_action_requests(value) or [{}]
            for action in actions:
                name = _read_field(action, "name") or "unknown"
                args = _read_field(action, "args") or {}
                description = _read_field(action, "description")
                print("\nTool execution requires approval")
                print(f"Tool: {name}")
                print(f"Args: {args}")
                if description:
                    print(f"Reason: {description}")
                answer = input("Allow this action? [y/N] ").strip().lower()
                if answer in {"y", "yes"}:
                    decisions.append({"type": "approve"})
                else:
                    decisions.append({"type": "reject", "message": "Rejected by user."})
        return decisions


class FakeAgentRuntime:
    def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            content=f"easy-claw dry run: {request.prompt}",
            thread_id=request.thread_id,
        )


class DeepAgentsRuntime:
    def __init__(self, reviewer: ApprovalReviewer | None = None) -> None:
        self._reviewer = reviewer or ConsoleApprovalReviewer()

    def run(self, request: AgentRequest) -> AgentResult:
        with self.open_session(request) as session:
            return session.run(request.prompt)

    def open_session(self, request: AgentRequest) -> DeepAgentSession:
        if request.model is None:
            raise RuntimeError("Set EASY_CLAW_MODEL before running chat without --dry-run.")
        if request.api_key is None:
            raise RuntimeError("Set EASY_CLAW_API_KEY before running chat without --dry-run.")
        if request.checkpoint_db_path is None:
            raise RuntimeError("checkpoint_db_path is required for DeepAgentsRuntime.")

        request.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        system_prompt = _build_system_prompt(request.memories)

        from deepagents import create_deep_agent
        from deepagents.backends import FilesystemBackend
        from langgraph.checkpoint.sqlite import SqliteSaver

        interrupt_on = {
            "edit_file": True,
            "write_file": True,
        }

        checkpointer_context = SqliteSaver.from_conn_string(str(request.checkpoint_db_path))
        checkpointer = checkpointer_context.__enter__()
        agent = create_deep_agent(
            model=_build_chat_model(request.model, request.base_url, request.api_key),
            system_prompt=system_prompt,
            skills=list(request.skill_sources) or None,
            backend=FilesystemBackend(root_dir=request.workspace_path, virtual_mode=True),
            checkpointer=checkpointer,
            interrupt_on=interrupt_on,
        )
        return DeepAgentSession(
            agent=agent,
            thread_id=request.thread_id,
            reviewer=self._reviewer,
            checkpointer_context=checkpointer_context,
        )


class DeepAgentSession:
    def __init__(
        self,
        *,
        agent: Any,
        thread_id: str,
        reviewer: ApprovalReviewer,
        checkpointer_context: object,
    ) -> None:
        self._agent = agent
        self._thread_id = thread_id
        self._reviewer = reviewer
        self._checkpointer_context = checkpointer_context

    def __enter__(self) -> DeepAgentSession:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._checkpointer_context.__exit__(None, None, None)

    def run(self, prompt: str) -> AgentResult:
        result = _invoke_with_approval(
            self._agent,
            {"messages": [{"role": "user", "content": prompt}]},
            config={"configurable": {"thread_id": self._thread_id}},
            reviewer=self._reviewer,
        )
        return AgentResult(
            content=_extract_last_message_content(result),
            thread_id=self._thread_id,
        )


def _build_chat_model(model: str, base_url: str, api_key: str) -> object:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _build_system_prompt(memories: Sequence[str]) -> str:
    sections = [
        "You are easy-claw, a Windows-first local personal AI workbench.",
        "Operate only inside the selected workspace unless the user explicitly approves otherwise.",
        "Do not execute commands or write files without human approval.",
    ]
    if memories:
        sections.append(
            "Explicit product memories:\n" + "\n".join(f"- {memory}" for memory in memories)
        )
    return "\n\n".join(sections)


def _extract_last_message_content(result: object) -> str:
    if not isinstance(result, dict):
        return str(result)

    messages = result.get("messages")
    if not messages:
        return str(result)

    last_message = messages[-1]
    content = getattr(last_message, "content", None)
    if content is None and isinstance(last_message, dict):
        content = last_message.get("content")
    return str(content or "")


def _invoke_with_approval(
    agent: Any,
    input_value: object,
    *,
    config: dict[str, object],
    reviewer: ApprovalReviewer,
) -> object:
    from langgraph.types import Command

    result = agent.invoke(input_value, config)
    while interrupts := _extract_interrupts(result):
        decisions = reviewer.review(interrupts)
        result = agent.invoke(Command(resume={"decisions": decisions}), config)
    return result


def _extract_interrupts(result: object) -> tuple[object, ...]:
    if not isinstance(result, dict):
        return ()
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return ()
    return tuple(interrupts)


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

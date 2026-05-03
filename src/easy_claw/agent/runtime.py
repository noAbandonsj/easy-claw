from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from easy_claw.agent.tools import build_agent_tools


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
    approval_mode: str = "permissive"
    execution_mode: str = "local"


@dataclass(frozen=True)
class AgentResult:
    content: str
    thread_id: str


@dataclass(frozen=True)
class StreamEvent:
    type: str
    content: str = ""
    tool_name: str | None = None
    tool_args: object | None = None
    tool_result: object | None = None
    thread_id: str | None = None


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

        agent_tools = build_agent_tools(
            workspace_path=request.workspace_path,
            cwd=request.workspace_path,
        )
        interrupt_on = _build_interrupt_on(request.approval_mode)

        checkpointer_context = SqliteSaver.from_conn_string(str(request.checkpoint_db_path))
        checkpointer = checkpointer_context.__enter__()
        agent = create_deep_agent(
            model=_build_chat_model(request.model, request.base_url, request.api_key),
            tools=agent_tools,
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

    def stream(self, prompt: str) -> Iterable[StreamEvent]:
        return _stream_with_approval(
            self._agent,
            {"messages": [{"role": "user", "content": prompt}]},
            config={"configurable": {"thread_id": self._thread_id}},
            reviewer=self._reviewer,
            thread_id=self._thread_id,
        )


def _build_chat_model(model: str, base_url: str, api_key: str) -> object:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _build_interrupt_on(approval_mode: str) -> dict[str, bool]:
    mode = approval_mode.strip().lower()
    if mode == "permissive":
        return {}
    if mode in {"balanced", "strict"}:
        return {
            "edit_file": True,
            "write_file": True,
            "run_command": True,
            "run_python": True,
            "write_report": True,
        }
    return {}


def _build_system_prompt(memories: Sequence[str]) -> str:
    sections = [
        "You are easy-claw, an agent-first Windows personal code assistant.",
        "The user should describe tasks naturally; do not ask them to manually run "
        "docs/tools/dev commands.",
        "Use available tools proactively to read files, run tests, inspect projects, "
        "search, and write reports.",
        "Operate inside the selected workspace unless the user explicitly asks for another path.",
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


def _stream_with_approval(
    agent: Any,
    input_value: object,
    *,
    config: dict[str, object],
    reviewer: ApprovalReviewer,
    thread_id: str,
) -> Iterable[StreamEvent]:
    from langgraph.types import Command

    content = ""
    next_input = input_value

    while True:
        interrupted = False
        for stream_item in agent.stream(next_input, config, stream_mode="messages"):
            interrupts = _extract_interrupts(stream_item)
            if interrupts:
                yield StreamEvent(type="approval_required", thread_id=thread_id)
                decisions = reviewer.review(interrupts)
                next_input = Command(resume={"decisions": decisions})
                interrupted = True
                break

            for event in _events_from_stream_item(stream_item, thread_id=thread_id):
                if event.type == "token":
                    content += event.content
                yield event

        if not interrupted:
            break

    yield StreamEvent(type="done", content=content, thread_id=thread_id)


def _events_from_stream_item(stream_item: object, *, thread_id: str) -> list[StreamEvent]:
    message = _message_from_stream_item(stream_item)
    events: list[StreamEvent] = []
    events.extend(_tool_call_events_from_message(message, thread_id=thread_id))

    tool_result = _tool_result_event_from_message(message, thread_id=thread_id)
    if tool_result is not None:
        events.append(tool_result)
        return events

    content = _text_from_message(message)
    if content:
        events.append(StreamEvent(type="token", content=content, thread_id=thread_id))
    return events


def _message_from_stream_item(stream_item: object) -> object:
    if isinstance(stream_item, tuple):
        return stream_item[0]
    return stream_item


def _text_from_message(message: object) -> str:
    content = _read_field(message, "content")
    if content is None:
        return ""
    return str(content)


def _tool_call_events_from_message(message: object, *, thread_id: str) -> list[StreamEvent]:
    tool_calls = _read_field(message, "tool_calls") or []
    additional_kwargs = _read_field(message, "additional_kwargs") or {}
    if isinstance(additional_kwargs, dict):
        tool_calls = tool_calls or additional_kwargs.get("tool_calls") or []

    events: list[StreamEvent] = []
    for raw_call in tool_calls:
        name, args = _parse_tool_call(raw_call)
        if name:
            events.append(
                StreamEvent(
                    type="tool_call_start",
                    tool_name=name,
                    tool_args=args,
                    thread_id=thread_id,
                )
            )
    return events


def _tool_result_event_from_message(
    message: object,
    *,
    thread_id: str,
) -> StreamEvent | None:
    role = _read_field(message, "role")
    message_type = _read_field(message, "type")
    tool_call_id = _read_field(message, "tool_call_id")
    if role != "tool" and message_type != "tool" and tool_call_id is None:
        return None

    content = _text_from_message(message)
    name = _read_field(message, "name") or _read_field(message, "tool_name") or "tool"
    return StreamEvent(
        type="tool_call_result",
        content=content,
        tool_name=str(name),
        tool_result=content,
        thread_id=thread_id,
    )


def _parse_tool_call(raw_call: object) -> tuple[str | None, object | None]:
    if isinstance(raw_call, dict):
        name = raw_call.get("name")
        args = raw_call.get("args")
        function = raw_call.get("function")
        if isinstance(function, dict):
            name = name or function.get("name")
            args = args if args is not None else function.get("arguments")
        return str(name) if name else None, _parse_tool_args(args)

    name = _read_field(raw_call, "name")
    args = _read_field(raw_call, "args")
    return str(name) if name else None, _parse_tool_args(args)


def _parse_tool_args(args: object) -> object | None:
    if not isinstance(args, str):
        return args
    try:
        return json.loads(args)
    except json.JSONDecodeError:
        return args


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

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from easy_claw.agent.middleware import build_agent_middleware
from easy_claw.agent.skill_tools import build_skill_summary, build_skill_tool_bundle
from easy_claw.agent.toolset import build_easy_claw_tools
from easy_claw.agent.types import ToolContext
from easy_claw.config import AppConfig
from easy_claw.skills import SkillSource


@dataclass(frozen=True)
class AgentRequest:
    prompt: str
    thread_id: str
    config: AppConfig | None
    workspace_path: Path | None = None
    skill_sources: Sequence[str] = field(default_factory=tuple)
    skill_source_records: Sequence[SkillSource] = field(default_factory=tuple)


@dataclass(frozen=True)
class AgentResult:
    content: str
    thread_id: str
    usage: dict[str, int] | None = None


@dataclass(frozen=True)
class StreamEvent:
    type: str
    content: str = ""
    tool_name: str | None = None
    tool_args: object | None = None
    tool_result: object | None = None
    thread_id: str | None = None
    usage: dict[str, int] | None = None


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


class LangChainAgentRuntime:
    def __init__(self, reviewer: ApprovalReviewer | None = None) -> None:
        self._reviewer = reviewer or ConsoleApprovalReviewer()

    def run(self, request: AgentRequest) -> AgentResult:
        with self.open_session(request) as session:
            return session.run(request.prompt)

    def open_session(self, request: AgentRequest) -> LangChainAgentSession:
        if request.config is None:
            raise RuntimeError("LangChainAgentRuntime 必须传入 config。")
        cfg = request.config
        if cfg.model is None:
            raise RuntimeError("运行聊天前请先设置 EASY_CLAW_MODEL。")
        if cfg.api_key is None:
            raise RuntimeError("运行聊天前请先设置 EASY_CLAW_API_KEY。")
        if cfg.checkpoint_db_path is None:
            raise RuntimeError("LangChainAgentRuntime 必须配置 checkpoint_db_path。")

        cfg.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        system_prompt = _build_system_prompt(
            skill_summary=build_skill_summary(request.skill_source_records),
        )
        workspace_path = request.workspace_path or cfg.default_workspace

        from langchain.agents import create_agent
        from langgraph.checkpoint.sqlite import SqliteSaver

        tool_bundle = build_easy_claw_tools(
            ToolContext(
                workspace_path=workspace_path,
                cwd=workspace_path,
                browser_enabled=cfg.browser_enabled,
                browser_headless=cfg.browser_headless,
                mcp_enabled=cfg.mcp_enabled,
                mcp_mode=cfg.mcp_mode,
                mcp_config_path=cfg.mcp_config_path,
            )
        )
        interrupt_on = _build_interrupt_on(cfg.approval_mode, tool_bundle.interrupt_on)
        skill_tool_bundle = build_skill_tool_bundle(
            skill_source_records=request.skill_source_records,
        )
        tools = [*tool_bundle.tools, *skill_tool_bundle.tools]

        stack = ExitStack()
        checkpointer = stack.enter_context(
            SqliteSaver.from_conn_string(str(cfg.checkpoint_db_path))
        )
        agent = create_agent(
            model=_build_chat_model(cfg.model, cfg.base_url, cfg.api_key),
            tools=tools,
            system_prompt=system_prompt,
            middleware=build_agent_middleware(
                max_model_calls=cfg.max_model_calls,
                max_tool_calls=cfg.max_tool_calls,
                interrupt_on=interrupt_on,
            ),
            checkpointer=checkpointer,
        )
        for cb in tool_bundle.cleanup:
            stack.callback(cb)
        return LangChainAgentSession(
            agent=agent,
            thread_id=request.thread_id,
            reviewer=self._reviewer,
            exit_stack=stack,
        )


class LangChainAgentSession:
    def __init__(
        self,
        *,
        agent: Any,
        thread_id: str,
        reviewer: ApprovalReviewer,
        exit_stack: ExitStack,
    ) -> None:
        self._agent = agent
        self._thread_id = thread_id
        self._reviewer = reviewer
        self._exit_stack = exit_stack

    def __enter__(self) -> LangChainAgentSession:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._exit_stack.close()

    def run(self, prompt: str) -> AgentResult:
        try:
            result = _invoke_with_approval(
                self._agent,
                {"messages": [{"role": "user", "content": prompt}]},
                config={"configurable": {"thread_id": self._thread_id}},
                reviewer=self._reviewer,
            )
            content, usage = _extract_last_message_info(result)
        except Exception as exc:
            content = _format_agent_runtime_error(exc)
            usage = None
        return AgentResult(
            content=content,
            thread_id=self._thread_id,
            usage=usage,
        )

    def stream(self, prompt: str) -> Iterable[StreamEvent]:
        return _stream_with_approval(
            self._agent,
            {"messages": [{"role": "user", "content": prompt}]},
            config={"configurable": {"thread_id": self._thread_id}},
            reviewer=self._reviewer,
            thread_id=self._thread_id,
        )


DeepAgentsRuntime = LangChainAgentRuntime
DeepAgentSession = LangChainAgentSession


def _build_chat_model(model: str, base_url: str, api_key: str) -> object:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _build_interrupt_on(
    approval_mode: str,
    tool_interrupt_on: Mapping[str, object],
) -> dict[str, object]:
    mode = approval_mode.strip().lower()
    if mode == "permissive":
        return {}
    if mode in {"balanced", "strict"}:
        return dict(tool_interrupt_on)
    return {}


def _build_system_prompt(*, skill_summary: str = "") -> str:
    parts = [
        "你是 easy-claw，一个 Windows 优先的个人代码助手。",
        "用户会用自然语言描述任务；不要要求用户手动运行 docs、tools 或 dev 命令。",
        "请主动使用可用工具读取文件、运行测试、分析项目和搜索网页。",
        "除非用户明确要求其他路径，否则请在当前工作区内操作。",
        "easy-claw skills 通过 list_skills 和 read_skill 工具提供；"
        "如果任务明显匹配某个 skill，请先读取完整说明再执行。",
        "如果已通过 MCP 配置 Basic Memory 工具（write_note、search_notes、read_note 等），"
        "请用它们记住重要事实，并在跨会话时检索过去信息。",
    ]
    if skill_summary:
        parts.append(skill_summary)
    return "\n\n".join(parts)


def _extract_last_message_info(result: object) -> tuple[str, dict[str, int] | None]:
    """从 agent 调用结果中提取回复内容和用量。"""
    if not isinstance(result, dict):
        return str(result), None

    messages = result.get("messages")
    if not messages:
        return str(result), None

    last_message = messages[-1]
    content = getattr(last_message, "content", None)
    if content is None and isinstance(last_message, dict):
        content = last_message.get("content")

    usage = _usage_from_message(last_message)
    return str(content or ""), usage


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
    usage: dict[str, int] | None = None
    next_input = input_value

    while True:
        interrupted = False
        try:
            for stream_item in agent.stream(
                next_input,
                config,
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                mode, payload = _stream_item_payload(stream_item)

                interrupts = _extract_interrupts(payload)
                if interrupts:
                    yield StreamEvent(type="approval_required", thread_id=thread_id)
                    decisions = reviewer.review(interrupts)
                    next_input = Command(resume={"decisions": decisions})
                    interrupted = True
                    break

                if mode == "updates":
                    msg = _last_completed_message(payload)
                    msg_usage = _usage_from_message(msg)
                    if msg_usage is not None:
                        usage = msg_usage
                    tool_result = _tool_result_event_from_message(
                        msg, thread_id=thread_id
                    )
                    if tool_result is not None:
                        yield tool_result
                else:
                    msg = _message_from_stream_item(stream_item)
                    msg_usage = _usage_from_message(msg)
                    if msg_usage is not None:
                        usage = msg_usage
                    for event in _events_from_message(msg, thread_id=thread_id):
                        if event.type == "token":
                            content += event.content
                        yield event
        except Exception as exc:
            error_content = _format_agent_runtime_error(exc)
            yield StreamEvent(type="error", content=error_content, thread_id=thread_id)
            if content:
                content = f"{content}\n{error_content}"
            else:
                content = error_content
            yield StreamEvent(type="done", content=content, thread_id=thread_id, usage=usage)
            return

        if not interrupted:
            break

    yield StreamEvent(type="done", content=content, thread_id=thread_id, usage=usage)


def _format_agent_runtime_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return f"Agent 执行失败：{message}"


def _events_from_message(message: object, *, thread_id: str) -> list[StreamEvent]:
    if message is None:
        return []
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
    mode, payload = _stream_item_payload(stream_item)
    if mode == "updates":
        return None
    if isinstance(payload, tuple):
        return payload[0]
    return payload


def _stream_item_payload(stream_item: object) -> tuple[str | None, object]:
    if isinstance(stream_item, dict) and "type" in stream_item:
        return stream_item["type"], stream_item["data"]
    if (
        isinstance(stream_item, tuple)
        and len(stream_item) == 2
        and isinstance(stream_item[0], str)
    ):
        return stream_item[0], stream_item[1]
    return None, stream_item


def _last_completed_message(payload: object) -> object | None:
    if not isinstance(payload, dict):
        return None
    for source in ("model", "tools"):
        update = payload.get(source)
        if isinstance(update, dict):
            messages = update.get("messages")
            if messages:
                return messages[-1]
    return None


def _usage_from_message(message: object) -> dict[str, int] | None:
    usage_metadata = _read_field(message, "usage_metadata")
    usage = _normalize_usage_metadata(usage_metadata)
    if usage is not None:
        return usage

    response_metadata = _read_field(message, "response_metadata")
    if isinstance(response_metadata, dict):
        usage = _normalize_usage_metadata(response_metadata.get("token_usage"))
        if usage is not None:
            return usage
        return _normalize_usage_metadata(response_metadata.get("usage"))
    return None


def _normalize_usage_metadata(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None

    input_tokens = _first_int(value, "input_tokens", "prompt_tokens", "input")
    output_tokens = _first_int(value, "output_tokens", "completion_tokens", "output")
    total_tokens = _first_int(value, "total_tokens", "total")
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    input_count = input_tokens or 0
    output_count = output_tokens or 0
    return {
        "input": input_count,
        "output": output_count,
        "total": total_tokens if total_tokens is not None else input_count + output_count,
    }


def _first_int(value: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, int):
            return raw
    return None


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
    name = _read_field(message, "name") or _read_field(message, "tool_name") or "工具"
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

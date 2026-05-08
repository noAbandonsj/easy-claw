from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from easy_claw.agent.middleware import build_agent_middleware
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


class DeepAgentsRuntime:
    def __init__(self, reviewer: ApprovalReviewer | None = None) -> None:
        self._reviewer = reviewer or ConsoleApprovalReviewer()

    def run(self, request: AgentRequest) -> AgentResult:
        with self.open_session(request) as session:
            return session.run(request.prompt)

    def open_session(self, request: AgentRequest) -> DeepAgentSession:
        if request.config is None:
            raise RuntimeError("DeepAgentsRuntime 必须传入 config。")
        cfg = request.config
        if cfg.model is None:
            raise RuntimeError("运行聊天前请先设置 EASY_CLAW_MODEL。")
        if cfg.api_key is None:
            raise RuntimeError("运行聊天前请先设置 EASY_CLAW_API_KEY。")
        if cfg.checkpoint_db_path is None:
            raise RuntimeError("DeepAgentsRuntime 必须配置 checkpoint_db_path。")

        cfg.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        system_prompt = _build_system_prompt()
        workspace_path = request.workspace_path or cfg.default_workspace

        from deepagents import create_deep_agent
        from langgraph.checkpoint.sqlite import SqliteSaver

        skill_sources = _request_skill_source_paths(request)

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

        stack = ExitStack()
        checkpointer = stack.enter_context(
            SqliteSaver.from_conn_string(str(cfg.checkpoint_db_path))
        )
        agent = create_deep_agent(
            model=_build_chat_model(cfg.model, cfg.base_url, cfg.api_key),
            tools=tool_bundle.tools,
            system_prompt=system_prompt,
            skills=skill_sources or None,
            middleware=build_agent_middleware(
                max_model_calls=cfg.max_model_calls,
                max_tool_calls=cfg.max_tool_calls,
            ),
            backend=_build_agent_backend(workspace_path, request.skill_source_records),
            checkpointer=checkpointer,
            interrupt_on=interrupt_on,
        )
        for cb in tool_bundle.cleanup:
            stack.callback(cb)
        return DeepAgentSession(
            agent=agent,
            thread_id=request.thread_id,
            reviewer=self._reviewer,
            exit_stack=stack,
        )


class DeepAgentSession:
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

    def __enter__(self) -> DeepAgentSession:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._exit_stack.close()

    def run(self, prompt: str) -> AgentResult:
        result = _invoke_with_approval(
            self._agent,
            {"messages": [{"role": "user", "content": prompt}]},
            config={"configurable": {"thread_id": self._thread_id}},
            reviewer=self._reviewer,
        )
        content, usage = _extract_last_message_info(result)
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


def _build_chat_model(model: str, base_url: str, api_key: str) -> object:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _request_skill_source_paths(request: AgentRequest) -> list[str]:
    paths: list[str] = []
    for source in request.skill_sources:
        if source not in paths:
            paths.append(source)
    for source in request.skill_source_records:
        if source.backend_path not in paths:
            paths.append(source.backend_path)
    return paths


def _build_agent_backend(
    workspace_path: Path,
    skill_source_records: Sequence[SkillSource],
) -> object:
    from deepagents.backends import CompositeBackend, FilesystemBackend, LocalShellBackend

    workspace = workspace_path.expanduser().resolve(strict=False)
    default_backend = LocalShellBackend(root_dir=workspace, virtual_mode=True)
    routes = {}
    for source in skill_source_records:
        if _is_under_workspace(source.filesystem_path, workspace):
            continue
        routes[source.backend_path] = FilesystemBackend(
            root_dir=source.filesystem_path,
            virtual_mode=True,
        )
    if not routes:
        return default_backend
    return CompositeBackend(default=default_backend, routes=routes)


def _is_under_workspace(path: Path, workspace: Path) -> bool:
    try:
        path.expanduser().resolve(strict=False).relative_to(workspace)
    except ValueError:
        return False
    return True


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


def _build_system_prompt() -> str:
    return "\n\n".join(
        [
            "你是 easy-claw，一个 Windows 优先的个人代码助手。",
            "用户会用自然语言描述任务；不要要求用户手动运行 docs、tools 或 dev 命令。",
            "请主动使用可用工具读取文件、运行测试、分析项目和搜索网页。",
            "除非用户明确要求其他路径，否则请在当前工作区内操作。",
            "如果已通过 MCP 配置 Basic Memory 工具（write_note、search_notes、read_note 等），"
            "请用它们记住重要事实，并在跨会话时检索过去信息。",
        ]
    )


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

    usage = None
    usage_meta = getattr(last_message, "usage_metadata", None)
    if isinstance(usage_meta, dict):
        usage = {
            "input": usage_meta.get("input_tokens", 0),
            "output": usage_meta.get("output_tokens", 0),
            "total": usage_meta.get("total_tokens", 0),
        }
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
        for stream_item in agent.stream(next_input, config, stream_mode="messages"):
            interrupts = _extract_interrupts(stream_item)
            if interrupts:
                yield StreamEvent(type="approval_required", thread_id=thread_id)
                decisions = reviewer.review(interrupts)
                next_input = Command(resume={"decisions": decisions})
                interrupted = True
                break

            msg = _message_from_stream_item(stream_item)
            msg_usage = getattr(msg, "usage_metadata", None)
            if isinstance(msg_usage, dict):
                usage = {
                    "input": msg_usage.get("input_tokens", 0),
                    "output": msg_usage.get("output_tokens", 0),
                    "total": msg_usage.get("total_tokens", 0),
                }

            for event in _events_from_stream_item(stream_item, thread_id=thread_id):
                if event.type == "token":
                    content += event.content
                yield event

        if not interrupted:
            break

    yield StreamEvent(type="done", content=content, thread_id=thread_id, usage=usage)


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

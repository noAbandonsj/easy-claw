from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from easy_claw.agent.approvals import (
    ApprovalReviewer,
    ConsoleApprovalReviewer,
    StaticApprovalReviewer,
)
from easy_claw.agent.middleware import build_agent_middleware
from easy_claw.agent.prompts import build_system_prompt as _build_system_prompt
from easy_claw.agent.skill_tools import build_skill_summary, build_skill_tool_bundle
from easy_claw.agent.streaming import (
    StreamEvent,
    _events_from_message,
    _extract_last_message_info,
    _format_agent_runtime_error,
    _invoke_with_approval,
    _stream_with_approval,
)
from easy_claw.agent.toolset import build_easy_claw_tools
from easy_claw.agent.types import ToolContext
from easy_claw.config import AppConfig
from easy_claw.skills import SkillSource

__all__ = [
    "AgentRequest",
    "AgentResult",
    "ApprovalReviewer",
    "ConsoleApprovalReviewer",
    "LangChainAgentRuntime",
    "LangChainAgentSession",
    "StaticApprovalReviewer",
    "StreamEvent",
    "_build_chat_model",
    "_build_interrupt_on",
    "_build_system_prompt",
    "_events_from_message",
    "_invoke_with_approval",
]


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
        chat_model = _build_chat_model(cfg.model, cfg.base_url, cfg.api_key)

        stack = ExitStack()
        checkpointer = stack.enter_context(
            SqliteSaver.from_conn_string(str(cfg.checkpoint_db_path))
        )
        agent = create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=system_prompt,
            middleware=build_agent_middleware(
                max_model_calls=cfg.max_model_calls,
                max_tool_calls=cfg.max_tool_calls,
                interrupt_on=interrupt_on,
                summarization_model=chat_model,
                workspace_path=str(workspace_path),
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
        try:
            self._exit_stack.close()
        except Exception:
            pass

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


def _build_chat_model(model: str, base_url: str, api_key: str) -> object:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        stream_usage=True,
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

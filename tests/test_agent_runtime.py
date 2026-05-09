from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from easy_claw.agent.runtime import (
    AgentRequest,
    AgentResult,
    LangChainAgentRuntime,
    LangChainAgentSession,
    StaticApprovalReviewer,
    StreamEvent,
    _build_chat_model,
    _build_interrupt_on,
    _events_from_message,
    _invoke_with_approval,
)
from easy_claw.config import AppConfig
from easy_claw.skills import SkillSource


def _test_config(*, tmp_path: Path, **kwargs: object) -> AppConfig:
    """Build a minimal AppConfig for tests."""
    defaults = {
        "cwd": tmp_path,
        "data_dir": tmp_path / "data",
        "product_db_path": tmp_path / "easy-claw.db",
        "checkpoint_db_path": tmp_path / "checkpoints.sqlite",
        "default_workspace": tmp_path,
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com",
        "api_key": "test-key",
        "mcp_mode": "disabled",
    }
    defaults.update(kwargs)
    return AppConfig(**defaults)


def test_langchain_runtime_is_available_as_agent_runtime_alias():
    from easy_claw.agent.protocols import AgentRuntime
    from easy_claw.agent.runtime import DeepAgentsRuntime, LangChainAgentRuntime

    runtime = LangChainAgentRuntime()

    assert isinstance(runtime, LangChainAgentRuntime)
    assert DeepAgentsRuntime is LangChainAgentRuntime
    assert hasattr(AgentRuntime, "run")
    assert hasattr(AgentRuntime, "open_session")


def test_deepagents_runtime_requires_model_configuration(tmp_path):
    runtime = LangChainAgentRuntime()
    config = _test_config(tmp_path=tmp_path, model=None)

    try:
        runtime.open_session(
            AgentRequest(
                prompt="hello",
                thread_id="thread-1",
                config=config,
            )
        )
    except RuntimeError as exc:
        assert "EASY_CLAW_MODEL" in str(exc)
    else:
        raise AssertionError("LangChainAgentRuntime should require EASY_CLAW_MODEL")


def test_build_chat_model_creates_openai_compatible_model(monkeypatch):
    model = _build_chat_model(
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        api_key="test-key",
    )

    assert model.model_name == "deepseek-v4-pro"
    assert str(model.openai_api_base).rstrip("/") == "https://api.deepseek.com"


def test_build_chat_model_works_with_custom_base_url(monkeypatch):
    model = _build_chat_model(
        model="moonshot-v1-128k",
        base_url="https://api.moonshot.cn/v1",
        api_key="test-key",
    )

    assert model.model_name == "moonshot-v1-128k"
    assert str(model.openai_api_base).rstrip("/") == "https://api.moonshot.cn/v1"


def test_build_interrupt_on_defaults_permissive_to_no_interrupts():
    assert (
        _build_interrupt_on(
            "permissive",
            {"run_command": True, "custom_risky_tool": True},
        )
        == {}
    )


def test_build_interrupt_on_balanced_uses_tool_bundle_policy():
    assert _build_interrupt_on(
        "balanced",
        {"run_command": True, "custom_risky_tool": True},
    ) == {"run_command": True, "custom_risky_tool": True}


@dataclass
class FakeInterrupt:
    value: object


class FakeAgent:
    def __init__(self):
        self.inputs = []

    def invoke(self, input_value, config):
        self.inputs.append(input_value)
        if len(self.inputs) == 1:
            return {
                "__interrupt__": (
                    FakeInterrupt(
                        {
                            "action_requests": [
                                {
                                    "name": "write_file",
                                    "args": {"file_path": "report.md"},
                                    "description": "write report",
                                }
                            ],
                            "review_configs": [
                                {
                                    "action_name": "write_file",
                                    "allowed_decisions": ["approve", "reject"],
                                }
                            ],
                        }
                    ),
                )
            }
        return {"messages": [{"role": "assistant", "content": "done"}]}


def test_invoke_with_approval_resumes_after_interrupt():
    agent = FakeAgent()
    reviewer = StaticApprovalReviewer(approve=True)

    result = _invoke_with_approval(
        agent,
        {"messages": [{"role": "user", "content": "write report"}]},
        config={"configurable": {"thread_id": "thread-1"}},
        reviewer=reviewer,
    )

    assert result["messages"][-1]["content"] == "done"
    assert isinstance(agent.inputs[1], Command)
    assert agent.inputs[1].resume == {"decisions": [{"type": "approve"}]}


def test_langchain_runtime_uses_create_agent_and_core_tools(tmp_path, monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self):
            self.invoke_count = 0

        def invoke(self, input_value, config):
            self.invoke_count += 1
            return {"messages": [{"role": "assistant", "content": "done"}]}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return FakeAgent()

    chat_model = FakeMessagesListChatModel(responses=[])
    monkeypatch.setattr(
        "easy_claw.agent.runtime._build_chat_model",
        lambda model, base_url, api_key: chat_model,
    )
    monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)

    config = _test_config(
        tmp_path=tmp_path,
        checkpoint_db_path=tmp_path / "checkpoints.sqlite",
    )
    result = LangChainAgentRuntime(reviewer=StaticApprovalReviewer(approve=True)).run(
        AgentRequest(
            prompt="hello",
            thread_id="thread-1",
            config=config,
            skill_sources=["/skills/core/"],
        )
    )

    assert result.content == "done"
    assert isinstance(captured["model"], FakeMessagesListChatModel)
    assert "skills" not in captured
    assert "backend" not in captured
    assert "interrupt_on" not in captured
    assert isinstance(captured["middleware"][0], ModelCallLimitMiddleware)
    assert captured["middleware"][0].run_limit == 40
    assert isinstance(captured["middleware"][1], ToolCallLimitMiddleware)
    assert captured["middleware"][1].run_limit == 100
    tool_names = {t.name for t in captured["tools"]}
    assert tool_names == {
        "search_web",
        "run_command",
        "run_python",
        "read_document",
        "list_skills",
        "read_skill",
    }


def test_langchain_runtime_does_not_route_external_skill_sources_through_backend(
    tmp_path,
    monkeypatch,
):
    captured = {}
    external_source = tmp_path / "external" / "skills"
    workspace = tmp_path / "workspace"
    external_source.mkdir(parents=True)
    workspace.mkdir()

    class FakeAgent:
        def invoke(self, input_value, config):
            return {"messages": [{"role": "assistant", "content": "done"}]}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return FakeAgent()

    chat_model = FakeMessagesListChatModel(responses=[])
    monkeypatch.setattr(
        "easy_claw.agent.runtime._build_chat_model",
        lambda model, base_url, api_key: chat_model,
    )
    monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)

    config = _test_config(
        tmp_path=tmp_path,
        default_workspace=workspace,
        checkpoint_db_path=tmp_path / "checkpoints.sqlite",
    )
    source = SkillSource(
        scope="user",
        label="user easy-claw",
        filesystem_path=external_source,
        backend_path="/easy-claw/skill-sources/external-skills/",
        skill_count=1,
    )

    result = LangChainAgentRuntime(reviewer=StaticApprovalReviewer(approve=True)).run(
        AgentRequest(
            prompt="hello",
            thread_id="thread-1",
            config=config,
            skill_source_records=[source],
        )
    )

    assert result.content == "done"
    assert "skills" not in captured
    assert "backend" not in captured
    assert "read_skill" in captured["system_prompt"]


def test_deepagents_runtime_uses_tool_bundle_and_closes_cleanup(tmp_path, monkeypatch):
    captured = {}
    fake_browser_tool = object()
    cleanup_calls = []

    class FakeAgent:
        def invoke(self, input_value, config):
            return {"messages": [{"role": "assistant", "content": "done"}]}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return FakeAgent()

    def fake_build_easy_claw_tools(context):
        captured["tool_context"] = context
        return type(
            "FakeToolBundle",
            (),
            {
                "tools": [fake_browser_tool],
                "cleanup": (lambda: cleanup_calls.append("cleanup"),),
                "interrupt_on": {"custom_risky_tool": True},
            },
        )()

    chat_model = FakeMessagesListChatModel(responses=[])
    monkeypatch.setattr(
        "easy_claw.agent.runtime._build_chat_model",
        lambda model, base_url, api_key: chat_model,
    )
    monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)
    monkeypatch.setattr(
        "easy_claw.agent.runtime.build_easy_claw_tools",
        fake_build_easy_claw_tools,
    )

    config = _test_config(
        tmp_path=tmp_path,
        checkpoint_db_path=tmp_path / "checkpoints.sqlite",
        approval_mode="balanced",
        browser_enabled=True,
        browser_headless=True,
        mcp_mode="auto",
    )
    with LangChainAgentRuntime(reviewer=StaticApprovalReviewer(approve=True)).open_session(
        AgentRequest(
            prompt="",
            thread_id="thread-1",
            config=config,
        )
    ) as session:
        result = session.run("hello")

    assert result.content == "done"
    assert captured["tool_context"].workspace_path == tmp_path
    assert captured["tool_context"].cwd == tmp_path
    assert captured["tool_context"].browser_enabled is True
    assert captured["tool_context"].browser_headless is True
    assert captured["tool_context"].mcp_enabled is False
    assert captured["tool_context"].mcp_mode == "auto"
    assert captured["tool_context"].mcp_config_path == "mcp_servers.json"
    assert fake_browser_tool in captured["tools"]
    assert "interrupt_on" not in captured
    assert any(isinstance(m, HumanInTheLoopMiddleware) for m in captured["middleware"])
    assert cleanup_calls == ["cleanup"]


def test_deepagents_session_reuses_agent_between_turns(tmp_path, monkeypatch):
    captured = {"create_count": 0}

    class FakeAgent:
        def __init__(self):
            self.prompts = []

        def invoke(self, input_value, config):
            self.prompts.append(input_value["messages"][0]["content"])
            return {"messages": [{"role": "assistant", "content": f"answer {len(self.prompts)}"}]}

    def fake_create_agent(**kwargs):
        captured["create_count"] += 1
        captured["agent"] = FakeAgent()
        return captured["agent"]

    chat_model = FakeMessagesListChatModel(responses=[])
    monkeypatch.setattr(
        "easy_claw.agent.runtime._build_chat_model",
        lambda model, base_url, api_key: chat_model,
    )
    monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)

    config = _test_config(
        tmp_path=tmp_path,
        checkpoint_db_path=tmp_path / "checkpoints.sqlite",
    )
    runtime = LangChainAgentRuntime(reviewer=StaticApprovalReviewer(approve=True))
    with runtime.open_session(
        AgentRequest(
            prompt="",
            thread_id="thread-1",
            config=config,
        )
    ) as session:
        first = session.run("first")
        second = session.run("second")

    assert first.content == "answer 1"
    assert second.content == "answer 2"
    assert captured["create_count"] == 1
    assert captured["agent"].prompts == ["first", "second"]


class FakeFailingInvokeAgent:
    def invoke(self, input_value, config):
        raise RuntimeError("tool backend died")


def test_deepagent_session_run_returns_error_result_when_agent_raises():
    session = LangChainAgentSession(
        agent=FakeFailingInvokeAgent(),
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    result = session.run("call broken tool")

    assert result == AgentResult(
        content="Agent 执行失败：tool backend died",
        thread_id="thread-1",
    )


@dataclass
class FakeStreamMessage:
    content: str


@dataclass
class FakeStreamMessageWithResponseUsage:
    content: str
    response_metadata: dict[str, object]


class FakeStreamingAgent:
    def __init__(self):
        self.inputs = []
        self.stream_modes = []

    def stream(self, input_value, config, stream_mode, version=None):
        self.inputs.append(input_value)
        self.stream_modes.append(stream_mode)
        yield FakeStreamMessage("hello ")
        yield (FakeStreamMessage("world"), {"langgraph_node": "agent"})


def test_stream_event_can_represent_token_and_done():
    token = StreamEvent(type="token", content="hello", thread_id="thread-1")
    done = StreamEvent(type="done", content="hello", thread_id="thread-1")

    assert token.type == "token"
    assert token.content == "hello"
    assert done.type == "done"
    assert done.thread_id == "thread-1"


def test_deepagent_session_stream_yields_tokens_and_done():
    agent = FakeStreamingAgent()
    session = LangChainAgentSession(
        agent=agent,
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    events = list(session.stream("say hello"))

    assert events == [
        StreamEvent(type="token", content="hello ", thread_id="thread-1"),
        StreamEvent(type="token", content="world", thread_id="thread-1"),
        StreamEvent(type="done", content="hello world", thread_id="thread-1"),
    ]
    assert agent.inputs == [{"messages": [{"role": "user", "content": "say hello"}]}]
    assert agent.stream_modes == [["messages", "updates"]]


class FakeStreamingUsageAgent:
    def stream(self, input_value, config, stream_mode, version=None):
        yield FakeStreamMessageWithResponseUsage(
            "hello",
            {
                "token_usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 3,
                    "total_tokens": 15,
                }
            },
        )


def test_deepagent_session_stream_extracts_response_metadata_token_usage():
    session = LangChainAgentSession(
        agent=FakeStreamingUsageAgent(),
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    events = list(session.stream("say hello"))

    assert events[-1] == StreamEvent(
        type="done",
        content="hello",
        thread_id="thread-1",
        usage={"input": 12, "output": 3, "total": 15},
    )


@dataclass
class FakeToolCallMessage:
    content: str
    tool_calls: list[dict[str, object]]


@dataclass
class FakeToolResultMessage:
    content: str
    name: str
    type: str = "tool"


def test_stream_item_with_tool_call_yields_tool_call_start():
    events = _events_from_message(
        FakeToolCallMessage(
            content="",
            tool_calls=[{"name": "read_document", "args": {"path": "README.md"}}],
        ),
        thread_id="thread-1",
    )

    assert events == [
        StreamEvent(
            type="tool_call_start",
            tool_name="read_document",
            tool_args={"path": "README.md"},
            thread_id="thread-1",
        )
    ]


def test_stream_item_with_tool_result_yields_tool_call_result():
    events = _events_from_message(
        FakeToolResultMessage(
            content="# Project\n\n" + ("x" * 50),
            name="read_document",
        ),
        thread_id="thread-1",
    )

    assert events == [
        StreamEvent(
            type="tool_call_result",
            content="# Project\n\n" + ("x" * 50),
            tool_name="read_document",
            tool_result="# Project\n\n" + ("x" * 50),
            thread_id="thread-1",
        )
    ]


class FakeStreamingToolResultAgent:
    def stream(self, input_value, config, stream_mode, version=None):
        yield FakeToolResultMessage(content="# Project", name="read_document")
        yield FakeStreamMessage("final answer")


def test_deepagent_session_stream_done_content_ignores_tool_results():
    session = LangChainAgentSession(
        agent=FakeStreamingToolResultAgent(),
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    events = list(session.stream("read README"))

    assert events[-1] == StreamEvent(
        type="done",
        content="final answer",
        thread_id="thread-1",
    )


class FakeStreamingFailureAgent:
    def stream(self, input_value, config, stream_mode, version=None):
        yield FakeToolCallMessage(
            content="",
            tool_calls=[{"name": "maps_weather", "args": {"city": "上海"}}],
        )
        raise RuntimeError("tool backend died")


def test_deepagent_session_stream_yields_error_event_when_agent_stream_raises():
    session = LangChainAgentSession(
        agent=FakeStreamingFailureAgent(),
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    events = list(session.stream("call broken mcp tool"))

    assert events == [
        StreamEvent(
            type="tool_call_start",
            tool_name="maps_weather",
            tool_args={"city": "上海"},
            thread_id="thread-1",
        ),
        StreamEvent(
            type="error",
            content="Agent 执行失败：tool backend died",
            thread_id="thread-1",
        ),
        StreamEvent(
            type="done",
            content="Agent 执行失败：tool backend died",
            thread_id="thread-1",
        ),
    ]


class FakeStreamingInterruptAgent:
    def __init__(self):
        self.inputs = []

    def stream(self, input_value, config, stream_mode, version=None):
        self.inputs.append(input_value)
        if len(self.inputs) == 1:
            yield {
                "__interrupt__": (
                    FakeInterrupt(
                        {
                            "action_requests": [
                                {
                                    "name": "run_command",
                                    "args": {"command": "pytest -q"},
                                    "description": "run tests",
                                }
                            ]
                        }
                    ),
                )
            }
            return
        yield FakeStreamMessage("approved")


def test_deepagent_session_stream_resumes_after_interrupt():
    agent = FakeStreamingInterruptAgent()
    session = LangChainAgentSession(
        agent=agent,
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    events = list(session.stream("run tests"))

    assert events == [
        StreamEvent(type="approval_required", thread_id="thread-1"),
        StreamEvent(type="token", content="approved", thread_id="thread-1"),
        StreamEvent(type="done", content="approved", thread_id="thread-1"),
    ]
    assert isinstance(agent.inputs[1], Command)
    assert agent.inputs[1].resume == {"decisions": [{"type": "approve"}]}


class ToolCallingFakeMessagesModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def test_langchain_session_stream_resumes_real_human_interrupt():
    @tool
    def risky_tool(value: str) -> str:
        """A test tool that requires approval."""
        return f"tool:{value}"

    agent = create_agent(
        model=ToolCallingFakeMessagesModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "risky_tool",
                            "args": {"value": "x"},
                            "id": "call-1",
                        }
                    ],
                ),
                AIMessage(content="approved"),
            ]
        ),
        tools=[risky_tool],
        middleware=[HumanInTheLoopMiddleware(interrupt_on={"risky_tool": True})],
        checkpointer=InMemorySaver(),
    )
    session = LangChainAgentSession(
        agent=agent,
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    events = list(session.stream("run risky tool"))

    assert StreamEvent(
        type="approval_required",
        thread_id="thread-1",
    ) in events
    assert events[-1] == StreamEvent(
        type="done",
        content="approved",
        thread_id="thread-1",
    )

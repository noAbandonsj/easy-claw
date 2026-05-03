from dataclasses import dataclass

from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langgraph.types import Command

from easy_claw.agent.runtime import (
    AgentRequest,
    DeepAgentSession,
    DeepAgentsRuntime,
    FakeAgentRuntime,
    StaticApprovalReviewer,
    StreamEvent,
    _build_chat_model,
    _build_interrupt_on,
    _events_from_stream_item,
    _invoke_with_approval,
)


def test_fake_agent_runtime_returns_deterministic_result(tmp_path):
    runtime = FakeAgentRuntime()

    result = runtime.run(
        AgentRequest(
            prompt="hello",
            thread_id="thread-1",
            workspace_path=tmp_path,
            model=None,
            base_url="https://api.deepseek.com",
            api_key=None,
            skill_sources=[],
            memories=[],
        )
    )

    assert result.content == "easy-claw dry run: hello"
    assert result.thread_id == "thread-1"


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
    assert _build_interrupt_on(
        "permissive",
        {"run_command": True, "custom_risky_tool": True},
    ) == {}


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


def test_deepagents_runtime_uses_native_skills_and_virtual_backend(tmp_path, monkeypatch):
    captured = {}

    class FakeBackend:
        def __init__(self, *, root_dir, virtual_mode):
            captured["backend_root_dir"] = root_dir
            captured["backend_virtual_mode"] = virtual_mode

    class FakeDeepAgent:
        def __init__(self):
            self.invoke_count = 0

        def invoke(self, input_value, config):
            self.invoke_count += 1
            return {"messages": [{"role": "assistant", "content": "done"}]}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return FakeDeepAgent()

    monkeypatch.setattr(
        "easy_claw.agent.runtime._build_chat_model",
        lambda model, base_url, api_key: "chat-model",
    )
    monkeypatch.setattr("deepagents.create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("deepagents.backends.FilesystemBackend", FakeBackend)

    result = DeepAgentsRuntime(reviewer=StaticApprovalReviewer(approve=True)).run(
        AgentRequest(
            prompt="hello",
            thread_id="thread-1",
            workspace_path=tmp_path,
            model="deepseek-v4-pro",
            base_url="https://api.deepseek.com",
            api_key="test-key",
            skill_sources=["/skills/core/"],
            memories=["Use Chinese."],
            checkpoint_db_path=tmp_path / "checkpoints.sqlite",
        )
    )

    assert result.content == "done"
    assert captured["model"] == "chat-model"
    assert captured["skills"] == ["/skills/core/"]
    assert captured["backend_root_dir"] == tmp_path
    assert captured["backend_virtual_mode"] is True
    assert captured["interrupt_on"] == {}
    assert isinstance(captured["middleware"][0], ModelCallLimitMiddleware)
    assert captured["middleware"][0].run_limit == 40
    assert isinstance(captured["middleware"][1], ToolCallLimitMiddleware)
    assert captured["middleware"][1].run_limit == 100
    assert len(captured["tools"]) == 5
    tool_names = {t.name for t in captured["tools"]}
    assert tool_names == {
        "search_web",
        "run_command",
        "run_python",
        "read_document",
        "write_report",
    }
    assert "Use Chinese." in captured["system_prompt"]


def test_deepagents_runtime_uses_tool_bundle_and_closes_cleanup(tmp_path, monkeypatch):
    captured = {}
    fake_browser_tool = object()
    cleanup_calls = []

    class FakeBackend:
        def __init__(self, *, root_dir, virtual_mode):
            pass

    class FakeDeepAgent:
        def invoke(self, input_value, config):
            return {"messages": [{"role": "assistant", "content": "done"}]}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return FakeDeepAgent()

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

    monkeypatch.setattr(
        "easy_claw.agent.runtime._build_chat_model",
        lambda model, base_url, api_key: "chat-model",
    )
    monkeypatch.setattr("deepagents.create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("deepagents.backends.FilesystemBackend", FakeBackend)
    monkeypatch.setattr(
        "easy_claw.agent.runtime.build_easy_claw_tools",
        fake_build_easy_claw_tools,
    )

    with DeepAgentsRuntime(reviewer=StaticApprovalReviewer(approve=True)).open_session(
        AgentRequest(
            prompt="",
            thread_id="thread-1",
            workspace_path=tmp_path,
            model="deepseek-v4-pro",
            base_url="https://api.deepseek.com",
            api_key="test-key",
            checkpoint_db_path=tmp_path / "checkpoints.sqlite",
            approval_mode="balanced",
            browser_enabled=True,
            browser_headless=True,
        )
    ) as session:
        result = session.run("hello")

    assert result.content == "done"
    assert captured["tool_context"].workspace_path == tmp_path
    assert captured["tool_context"].cwd == tmp_path
    assert captured["tool_context"].browser_enabled is True
    assert captured["tool_context"].browser_headless is True
    assert fake_browser_tool in captured["tools"]
    assert captured["interrupt_on"] == {"custom_risky_tool": True}
    assert cleanup_calls == ["cleanup"]


def test_deepagents_session_reuses_agent_between_turns(tmp_path, monkeypatch):
    captured = {"create_count": 0}

    class FakeBackend:
        def __init__(self, *, root_dir, virtual_mode):
            pass

    class FakeDeepAgent:
        def __init__(self):
            self.prompts = []

        def invoke(self, input_value, config):
            self.prompts.append(input_value["messages"][0]["content"])
            return {"messages": [{"role": "assistant", "content": f"answer {len(self.prompts)}"}]}

    def fake_create_deep_agent(**kwargs):
        captured["create_count"] += 1
        captured["agent"] = FakeDeepAgent()
        return captured["agent"]

    monkeypatch.setattr(
        "easy_claw.agent.runtime._build_chat_model",
        lambda model, base_url, api_key: "chat-model",
    )
    monkeypatch.setattr("deepagents.create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("deepagents.backends.FilesystemBackend", FakeBackend)

    runtime = DeepAgentsRuntime(reviewer=StaticApprovalReviewer(approve=True))
    with runtime.open_session(
        AgentRequest(
            prompt="",
            thread_id="thread-1",
            workspace_path=tmp_path,
            model="deepseek-v4-pro",
            base_url="https://api.deepseek.com",
            api_key="test-key",
            checkpoint_db_path=tmp_path / "checkpoints.sqlite",
        )
    ) as session:
        first = session.run("first")
        second = session.run("second")

    assert first.content == "answer 1"
    assert second.content == "answer 2"
    assert captured["create_count"] == 1
    assert captured["agent"].prompts == ["first", "second"]


@dataclass
class FakeStreamMessage:
    content: str


class NullCheckpointerContext:
    def __exit__(self, exc_type, exc, traceback):
        pass


class FakeStreamingAgent:
    def __init__(self):
        self.inputs = []
        self.stream_modes = []

    def stream(self, input_value, config, stream_mode):
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
    session = DeepAgentSession(
        agent=agent,
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        checkpointer_context=NullCheckpointerContext(),
    )

    events = list(session.stream("say hello"))

    assert events == [
        StreamEvent(type="token", content="hello ", thread_id="thread-1"),
        StreamEvent(type="token", content="world", thread_id="thread-1"),
        StreamEvent(type="done", content="hello world", thread_id="thread-1"),
    ]
    assert agent.inputs == [{"messages": [{"role": "user", "content": "say hello"}]}]
    assert agent.stream_modes == ["messages"]


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
    events = _events_from_stream_item(
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
    events = _events_from_stream_item(
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
    def stream(self, input_value, config, stream_mode):
        yield FakeToolResultMessage(content="# Project", name="read_document")
        yield FakeStreamMessage("final answer")


def test_deepagent_session_stream_done_content_ignores_tool_results():
    session = DeepAgentSession(
        agent=FakeStreamingToolResultAgent(),
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        checkpointer_context=NullCheckpointerContext(),
    )

    events = list(session.stream("read README"))

    assert events[-1] == StreamEvent(
        type="done",
        content="final answer",
        thread_id="thread-1",
    )


class FakeStreamingInterruptAgent:
    def __init__(self):
        self.inputs = []

    def stream(self, input_value, config, stream_mode):
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
    session = DeepAgentSession(
        agent=agent,
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        checkpointer_context=NullCheckpointerContext(),
    )

    events = list(session.stream("run tests"))

    assert events == [
        StreamEvent(type="approval_required", thread_id="thread-1"),
        StreamEvent(type="token", content="approved", thread_id="thread-1"),
        StreamEvent(type="done", content="approved", thread_id="thread-1"),
    ]
    assert isinstance(agent.inputs[1], Command)
    assert agent.inputs[1].resume == {"decisions": [{"type": "approve"}]}

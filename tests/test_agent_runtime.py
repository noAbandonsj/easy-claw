from dataclasses import dataclass

import pytest
from langgraph.types import Command

from easy_claw.agent.runtime import (
    AgentRequest,
    DeepAgentSession,
    DeepAgentsRuntime,
    FakeAgentRuntime,
    StaticApprovalReviewer,
    StreamEvent,
    _build_chat_model,
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
    assert set(captured["interrupt_on"]) == {"edit_file", "write_file", "run_command", "run_python", "write_report"}
    assert len(captured["tools"]) == 5
    tool_names = {t.name for t in captured["tools"]}
    assert tool_names == {"search_web", "run_command", "run_python", "read_document", "write_report"}
    assert "Use Chinese." in captured["system_prompt"]


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
            return {
                "messages": [
                    {"role": "assistant", "content": f"answer {len(self.prompts)}"}
                ]
            }

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

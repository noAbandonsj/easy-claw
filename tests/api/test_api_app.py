import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from easy_claw.agent.streaming import StreamEvent
from easy_claw.api.app import create_app
from easy_claw.api.websocket import next_stream_event_or_none as _next_stream_event_or_none
from easy_claw.api.websocket import parse_client_message
from easy_claw.cli.slash import get_slash_command_specs
from easy_claw.config import AppConfig
from easy_claw.skills import SkillSource
from easy_claw.storage.repositories import SessionRecord


def _test_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model="deepseek-v4-pro",
        base_url="https://api.example.com",
        api_key="sk-test",
        mcp_mode="disabled",
    )


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_session_endpoint_uses_repository_lookup(monkeypatch):
    record = SessionRecord(
        id="session-1",
        title="Review",
        workspace_path="D:/workspace",
        model="test:model",
        created_at="2026-05-02T00:00:00+00:00",
        updated_at="2026-05-02T00:00:00+00:00",
    )

    class FakeSessionRepository:
        def __init__(self, db_path):
            self.db_path = db_path

        def get_session(self, session_id):
            assert session_id == "session-1"
            return record

        def list_sessions(self):
            raise AssertionError("GET /sessions/{id} should not scan list_sessions()")

    monkeypatch.setattr("easy_claw.api.app.initialize_product_db", lambda db_path: None)
    monkeypatch.setattr("easy_claw.api.app.SessionRepository", FakeSessionRepository)
    client = TestClient(create_app())

    response = client.get("/sessions/session-1")

    assert response.status_code == 200
    assert response.json()["id"] == "session-1"


def test_runs_endpoint_is_removed():
    client = TestClient(create_app())

    response = client.post("/runs", json={"prompt": "总结", "document_paths": ["README.md"]})

    assert response.status_code == 404


def test_uvicorn_websocket_protocol_dependency_is_importable():
    from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol

    assert AutoWebSocketsProtocol is not None


def test_slash_commands_endpoint_uses_cli_registry(tmp_path):
    client = TestClient(create_app(_test_config(tmp_path)))

    response = client.get("/slash-commands")

    assert response.status_code == 200
    assert response.json() == [command.__dict__ for command in get_slash_command_specs()]
    command_names = {command["name"] for command in response.json()}
    assert {"/skills", "/mcp", "/browser", "/sessions", "/resume"}.issubset(command_names)


def test_web_capability_endpoints_return_structured_data(tmp_path, monkeypatch):
    source = SkillSource(
        scope="project",
        label="project easy-claw",
        filesystem_path=tmp_path / ".easy-claw" / "skills",
        backend_path="/.easy-claw/skills/",
        skill_count=2,
    )
    record = SessionRecord(
        id="abcdef123456",
        title="Web resume",
        workspace_path=str(tmp_path),
        model="deepseek-v4-pro",
        created_at="2026-05-02T00:00:00+00:00",
        updated_at="2026-05-02T00:00:00+00:00",
    )

    class FakeSessionRepository:
        def __init__(self, db_path):
            self.db_path = db_path

        def list_sessions(self):
            return [record]

        def get_session(self, session_id):
            return record if session_id == record.id else None

    monkeypatch.setattr("easy_claw.api.app.initialize_product_db", lambda db_path: None)
    monkeypatch.setattr("easy_claw.api.app.SessionRepository", FakeSessionRepository)
    monkeypatch.setattr("easy_claw.api.app.resolve_skill_sources", lambda **kwargs: [source])
    monkeypatch.setattr(
        "easy_claw.api.app._check_playwright_browsers",
        lambda *, headless: not headless,
    )
    client = TestClient(create_app(_test_config(tmp_path)))

    assert client.get("/skills").json()["sources"][0]["label"] == "project easy-claw"
    assert client.get("/mcp").json()["mode"] == "disabled"

    browser = client.get("/browser").json()
    assert browser["enabled"] is False
    assert browser["chromium_installed"] is True
    assert browser["chromium_headless_installed"] is False

    resolved = client.get("/sessions/resolve/abcdef").json()
    assert resolved["id"] == "abcdef123456"


def test_doctor_endpoint_returns_web_safe_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "easy_claw.api.app._check_playwright_browsers",
        lambda *, headless: not headless,
    )
    client = TestClient(create_app(_test_config(tmp_path)))

    response = client.get("/doctor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["workspace"] == str(tmp_path)
    assert payload["api_key_configured"] is True
    assert "sk-test" not in json.dumps(payload)
    assert payload["browser"]["chromium_installed"] is True
    assert payload["browser"]["chromium_headless_installed"] is False


def test_save_conversation_endpoint_writes_markdown(tmp_path):
    client = TestClient(create_app(_test_config(tmp_path)))
    save_path = tmp_path / "exports" / "chat.md"

    response = client.post(
        "/conversation/save",
        json={
            "path": str(save_path),
            "session_id": "session-1",
            "workspace_path": str(tmp_path),
            "model": "deepseek-v4-pro",
            "messages": [
                {"kind": "user", "content": "你好"},
                {"kind": "assistant", "content": "你好，我能帮你。"},
                {"kind": "tool", "name": "run_command", "result": "ok"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["path"] == str(save_path)
    exported = save_path.read_text(encoding="utf-8")
    assert "# easy-claw 对话记录" in exported
    assert "**用户：**" in exported
    assert "你好，我能帮你。" in exported
    assert "run_command" not in exported


def test_resolve_workspace_endpoint_validates_directory(tmp_path):
    client = TestClient(create_app(_test_config(tmp_path)))
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    response = client.post("/workspace/resolve", json={"path": str(workspace)})
    missing = client.post("/workspace/resolve", json={"path": str(tmp_path / "missing")})

    assert response.status_code == 200
    assert response.json()["workspace_path"] == str(workspace)
    assert missing.status_code == 400
    assert missing.json()["detail"] == "不是目录"


def test_delete_session_endpoint_removes_session_and_checkpoint(tmp_path, monkeypatch):
    config = _test_config(tmp_path)
    from easy_claw.storage.db import initialize_product_db
    from easy_claw.storage.repositories import SessionRepository

    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)
    session = repo.create_session(
        workspace_path=str(tmp_path),
        model="deepseek-v4-pro",
        title="待删除",
    )
    deleted_threads = []
    monkeypatch.setattr(
        "easy_claw.api.app._delete_checkpoint_thread",
        lambda thread_id, checkpoint_db_path: deleted_threads.append(
            (thread_id, checkpoint_db_path)
        ),
    )
    client = TestClient(create_app(config))

    response = client.delete(f"/sessions/{session.id[:8]}")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["session"]["id"] == session.id
    assert repo.get_session(session.id) is None
    assert deleted_threads == [(session.id, config.checkpoint_db_path)]


def test_websocket_chat_passes_resolved_skill_source_records(tmp_path, monkeypatch):
    source_root = tmp_path / ".easy-claw" / "skills"
    source_root.mkdir(parents=True)
    source = SkillSource(
        scope="project",
        label="project easy-claw",
        filesystem_path=source_root,
        backend_path="/.easy-claw/skills/",
        skill_count=1,
    )
    captured_requests = []

    class FakeSession:
        def stream(self, text):
            yield StreamEvent(type="done", content="", thread_id="thread-1")

        def close(self):
            pass

    class FakeRuntime:
        def __init__(self, reviewer):
            self.reviewer = reviewer

        def open_session(self, request):
            captured_requests.append(request)
            return FakeSession()

    def fake_resolve_skill_sources(*, app_root, workspace_root, home_dir=None):
        assert app_root == tmp_path
        assert workspace_root == tmp_path
        return [source]

    monkeypatch.setattr("easy_claw.api.app.LangChainAgentRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.api.app.resolve_skill_sources", fake_resolve_skill_sources)
    client = TestClient(create_app(_test_config(tmp_path)))

    with client.websocket_connect("/ws/chat") as websocket:
        websocket.receive_json()
        websocket.close()

    assert captured_requests[0].skill_sources == ()
    assert captured_requests[0].skill_source_records == [source]


def test_websocket_chat_can_resume_existing_session_by_prefix(tmp_path, monkeypatch):
    record = SessionRecord(
        id="resume123456",
        title="Existing web chat",
        workspace_path=str(tmp_path),
        model="deepseek-v4-pro",
        created_at="2026-05-02T00:00:00+00:00",
        updated_at="2026-05-02T00:00:00+00:00",
    )
    captured_requests = []

    class FakeSessionRepository:
        def __init__(self, db_path):
            self.db_path = db_path

        def get_session(self, session_id):
            return record if session_id == record.id else None

        def list_sessions(self):
            return [record]

        def create_session(self, **kwargs):
            raise AssertionError("resume should not create a new session")

    class FakeSession:
        def close(self):
            pass

        def stream(self, text):
            yield StreamEvent(type="done", thread_id=record.id)

    class FakeRuntime:
        def __init__(self, reviewer):
            self.reviewer = reviewer

        def open_session(self, request):
            captured_requests.append(request)
            return FakeSession()

    monkeypatch.setattr("easy_claw.api.app.initialize_product_db", lambda db_path: None)
    monkeypatch.setattr("easy_claw.api.app.SessionRepository", FakeSessionRepository)
    monkeypatch.setattr("easy_claw.api.app.LangChainAgentRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.api.app.resolve_skill_sources", lambda **kwargs: [])
    client = TestClient(create_app(_test_config(tmp_path)))

    with client.websocket_connect("/ws/chat?session_id=resume") as websocket:
        banner = websocket.receive_json()
        websocket.close()

    assert banner["session_id"] == "resume12"
    assert captured_requests[0].thread_id == record.id


def test_websocket_chat_uses_web_workspace_and_model_overrides(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured_requests = []

    class FakeSession:
        def stream(self, text):
            yield StreamEvent(type="done", content="", thread_id="thread-1")

        def close(self):
            pass

    class FakeRuntime:
        def __init__(self, reviewer):
            self.reviewer = reviewer

        def open_session(self, request):
            captured_requests.append(request)
            return FakeSession()

    monkeypatch.setattr("easy_claw.api.app.LangChainAgentRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.api.app.resolve_skill_sources", lambda **kwargs: [])
    client = TestClient(create_app(_test_config(tmp_path)))

    with client.websocket_connect(
        f"/ws/chat?workspace_path={workspace}&model=web-model"
    ) as websocket:
        banner = websocket.receive_json()
        websocket.close()

    assert banner["workspace"] == str(workspace)
    assert banner["model"] == "web-model"
    assert captured_requests[0].config.default_workspace == workspace
    assert captured_requests[0].config.model == "web-model"


def test_parse_client_message_accepts_structured_prompt():
    assert parse_client_message(json.dumps({"type": "prompt", "content": "你好"})) == {
        "type": "prompt",
        "content": "你好",
    }
    assert parse_client_message("你好") == {"type": "prompt", "content": "你好"}


def test_websocket_chat_uses_structured_prompt_content(tmp_path, monkeypatch):
    captured_prompts = []

    class FakeSession:
        def close(self):
            pass

        def stream(self, text):
            captured_prompts.append(text)
            yield StreamEvent(type="done", content=text, thread_id="thread-1")

    class FakeRuntime:
        def __init__(self, reviewer):
            self.reviewer = reviewer

        def open_session(self, request):
            return FakeSession()

    monkeypatch.setattr("easy_claw.api.app.LangChainAgentRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.api.app.resolve_skill_sources", lambda **kwargs: [])
    client = TestClient(create_app(_test_config(tmp_path)))

    with client.websocket_connect("/ws/chat") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "prompt", "content": "结构化消息"})
        websocket.receive_json()
        websocket.close()

    assert captured_prompts == ["结构化消息"]


def test_websocket_chat_reports_runtime_setup_error(tmp_path, monkeypatch):
    class FakeRuntime:
        def __init__(self, reviewer):
            self.reviewer = reviewer

        def open_session(self, request):
            raise RuntimeError("运行聊天前请先设置 EASY_CLAW_MODEL。")

    monkeypatch.setattr("easy_claw.api.app.LangChainAgentRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.api.app.resolve_skill_sources", lambda **kwargs: [])
    client = TestClient(create_app(_test_config(tmp_path)))

    with client.websocket_connect("/ws/chat") as websocket:
        websocket.receive_json()
        error = websocket.receive_json()

    assert error == {
        "type": "error",
        "content": "运行聊天前请先设置 EASY_CLAW_MODEL。",
    }


def test_next_stream_event_or_none_returns_event_from_executor():
    event = StreamEvent(type="done", content="ok")

    async def call_in_executor():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _next_stream_event_or_none, iter([event]))

    assert asyncio.run(call_in_executor()) == event


def test_next_stream_event_or_none_returns_none_from_executor_when_exhausted():
    async def call_in_executor():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _next_stream_event_or_none, iter(()))

    assert asyncio.run(call_in_executor()) is None

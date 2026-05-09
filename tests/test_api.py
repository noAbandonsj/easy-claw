import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from easy_claw.agent.runtime import StreamEvent
from easy_claw.api.main import _next_stream_event_or_none, create_app
from easy_claw.cli_slash import get_slash_command_specs
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

    monkeypatch.setattr("easy_claw.api.main.initialize_product_db", lambda db_path: None)
    monkeypatch.setattr("easy_claw.api.main.SessionRepository", FakeSessionRepository)
    client = TestClient(create_app())

    response = client.get("/sessions/session-1")

    assert response.status_code == 200
    assert response.json()["id"] == "session-1"


def test_runs_endpoint_is_removed():
    client = TestClient(create_app())

    response = client.post("/runs", json={"prompt": "总结", "document_paths": ["README.md"]})

    assert response.status_code == 404


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

    monkeypatch.setattr("easy_claw.api.main.initialize_product_db", lambda db_path: None)
    monkeypatch.setattr("easy_claw.api.main.SessionRepository", FakeSessionRepository)
    monkeypatch.setattr("easy_claw.api.main.resolve_skill_sources", lambda **kwargs: [source])
    monkeypatch.setattr(
        "easy_claw.api.main._check_playwright_browsers",
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

    monkeypatch.setattr("easy_claw.api.main.LangChainAgentRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.api.main.resolve_skill_sources", fake_resolve_skill_sources)
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

    monkeypatch.setattr("easy_claw.api.main.initialize_product_db", lambda db_path: None)
    monkeypatch.setattr("easy_claw.api.main.SessionRepository", FakeSessionRepository)
    monkeypatch.setattr("easy_claw.api.main.LangChainAgentRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.api.main.resolve_skill_sources", lambda **kwargs: [])
    client = TestClient(create_app(_test_config(tmp_path)))

    with client.websocket_connect("/ws/chat?session_id=resume") as websocket:
        banner = websocket.receive_json()
        websocket.close()

    assert banner["session_id"] == "resume12"
    assert captured_requests[0].thread_id == record.id


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

from fastapi.testclient import TestClient

from easy_claw.agent.runtime import AgentResult
from easy_claw.api.main import create_app
from easy_claw.config import AppConfig
from easy_claw.storage.repositories import AuditRepository, SessionRecord


class FakeConverter:
    def convert(self, path):
        class Result:
            text_content = "# Converted"

        return Result()


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


def test_create_run_requires_prompt_and_documents(tmp_path):
    config = AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model=None,
        base_url="https://api.deepseek.com",
        api_key="test-key",
    )
    client = TestClient(create_app(config))

    response = client.post("/runs", json={"prompt": "总结", "document_paths": []})

    assert response.status_code == 400


def test_create_run_uses_runtime_and_writes_output(tmp_path, monkeypatch):
    config = AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        api_key="test-key",
    )
    (tmp_path / "README.md").write_text("# Project", encoding="utf-8")

    class FakeRuntime:
        def run(self, request):
            assert "# Project" in request.prompt
            return AgentResult(content="# Summary", thread_id=request.thread_id)

    monkeypatch.setattr("easy_claw.workflows.document_runs.DeepAgentsRuntime", FakeRuntime)
    client = TestClient(create_app(config))

    response = client.post(
        "/runs",
        json={
            "prompt": "总结",
            "document_paths": ["README.md"],
            "output_path": "reports/summary.md",
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == "# Summary"
    assert response.json()["output_path"] == "reports/summary.md"
    assert (tmp_path / "reports" / "summary.md").read_text(encoding="utf-8") == "# Summary"
    events = [
        log.event_type for log in AuditRepository(config.product_db_path).list_logs()
    ]
    assert "document_read" in events
    assert "agent_run" in events
    assert "report_written" in events


def test_create_run_converts_non_text_documents(tmp_path, monkeypatch):
    config = AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        api_key="test-key",
    )
    (tmp_path / "report.docx").write_bytes(b"fake")

    class FakeRuntime:
        def run(self, request):
            assert "# Converted" in request.prompt
            return AgentResult(content="# Summary", thread_id=request.thread_id)

    monkeypatch.setattr("easy_claw.workflows.document_runs.DeepAgentsRuntime", FakeRuntime)
    monkeypatch.setattr(
        "easy_claw.tools.documents._create_markitdown_converter",
        lambda: FakeConverter(),
    )
    client = TestClient(create_app(config))

    response = client.post(
        "/runs",
        json={"prompt": "总结", "document_paths": ["report.docx"]},
    )

    assert response.status_code == 200
    events = [
        log.event_type for log in AuditRepository(config.product_db_path).list_logs()
    ]
    assert "document_converted" in events


def test_create_run_continues_after_unreadable_document(tmp_path, monkeypatch):
    config = AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        api_key="test-key",
    )
    (tmp_path / "README.md").write_text("# Project", encoding="utf-8")
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe\xff")

    class FakeRuntime:
        def run(self, request):
            assert "# Project" in request.prompt
            assert "bad.txt" not in request.prompt
            return AgentResult(content="# Summary", thread_id=request.thread_id)

    monkeypatch.setattr("easy_claw.workflows.document_runs.DeepAgentsRuntime", FakeRuntime)
    client = TestClient(create_app(config), raise_server_exceptions=False)

    response = client.post(
        "/runs",
        json={"prompt": "总结", "document_paths": ["README.md", "bad.txt"]},
    )

    assert response.status_code == 200
    assert response.json()["document_errors"][0]["path"] == "bad.txt"

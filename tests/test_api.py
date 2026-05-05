import asyncio

from fastapi.testclient import TestClient

from easy_claw.agent.runtime import StreamEvent
from easy_claw.api.main import _next_stream_event_or_none, create_app
from easy_claw.storage.repositories import SessionRecord


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

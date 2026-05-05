from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from easy_claw.agent.runtime import (
    AgentRequest,
    DeepAgentsRuntime,
    StaticApprovalReviewer,
    StreamEvent,
)
from easy_claw.config import AppConfig, load_config
from easy_claw.skills import discover_skill_sources
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import SessionRepository

_STATIC_DIR = Path(__file__).resolve().parent / "static"


class CreateSessionRequest(BaseModel):
    workspace_path: str | None = None
    model: str | None = None
    title: str = "New Session"


def _event_to_dict(event: StreamEvent) -> dict[str, object]:
    msg: dict[str, object] = {"type": event.type}
    if event.content:
        msg["content"] = event.content
    if event.tool_name:
        msg["tool_name"] = event.tool_name
    if event.tool_args is not None:
        msg["tool_args"] = event.tool_args
    if event.tool_result is not None:
        msg["tool_result"] = event.tool_result
    if event.usage:
        msg["usage"] = event.usage
    return msg


def _next_stream_event_or_none(stream_iter: Iterator[StreamEvent]) -> StreamEvent | None:
    try:
        return next(stream_iter)
    except StopIteration:
        return None


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or load_config()
    app = FastAPI(title="easy-claw", version="0.5.0")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/sessions")
    def list_sessions() -> list[dict[str, str | None]]:
        initialize_product_db(app_config.product_db_path)
        repo = SessionRepository(app_config.product_db_path)
        return [session.__dict__ for session in repo.list_sessions()]

    @app.post("/sessions")
    def create_session(request: CreateSessionRequest) -> dict[str, str | None]:
        initialize_product_db(app_config.product_db_path)
        repo = SessionRepository(app_config.product_db_path)
        workspace_path = request.workspace_path or str(app_config.default_workspace)
        model = request.model or app_config.model
        return repo.create_session(
            workspace_path=workspace_path,
            model=model,
            title=request.title,
        ).__dict__

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, str | None]:
        initialize_product_db(app_config.product_db_path)
        repo = SessionRepository(app_config.product_db_path)
        session = repo.get_session(session_id)
        if session is not None:
            return session.__dict__
        raise HTTPException(status_code=404, detail="Session not found")

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket) -> None:
        await websocket.accept()

        config = app_config or load_config()
        initialize_product_db(config.product_db_path)

        session_repo = SessionRepository(config.product_db_path)
        session = session_repo.create_session(
            workspace_path=str(config.default_workspace),
            model=config.model,
            title="Web Chat",
        )

        skill_sources = discover_skill_sources(config.cwd / "skills", config.default_workspace)
        runtime = DeepAgentsRuntime(reviewer=StaticApprovalReviewer(approve=True))

        await websocket.send_json(
            {
                "type": "banner",
                "model": config.model,
                "workspace": str(config.default_workspace),
                "version": "0.5.0",
                "session_id": session.id[:8],
            }
        )

        agent_session = runtime.open_session(
            AgentRequest(
                prompt="",
                thread_id=session.id,
                config=config,
                skill_sources=skill_sources,
            )
        )

        try:
            while True:
                text = await websocket.receive_text()
                if not text.strip():
                    continue

                # Run the synchronous stream iterator in a thread so the
                # asyncio event loop is not blocked while waiting for LLM
                # tokens.  Events are forwarded to the WebSocket as they
                # arrive.
                loop = asyncio.get_running_loop()
                stream_iter = agent_session.stream(text)
                while True:
                    event = await loop.run_in_executor(
                        None,
                        _next_stream_event_or_none,
                        stream_iter,
                    )
                    if event is None:
                        break
                    await websocket.send_json(_event_to_dict(event))
        except WebSocketDisconnect:
            pass
        finally:
            agent_session.close()

    app.mount("/static", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app


app = create_app()

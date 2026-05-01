from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from easy_claw.config import AppConfig, load_config
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import SessionRepository


class CreateSessionRequest(BaseModel):
    workspace_path: str | None = None
    model: str | None = None
    title: str = "New Session"


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or load_config()
    app = FastAPI(title="easy-claw", version="0.1.0")

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

    return app


app = create_app()

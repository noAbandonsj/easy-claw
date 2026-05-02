from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from easy_claw.config import AppConfig, load_config
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import SessionRepository
from easy_claw.workflows.document_runs import NoReadableDocumentsError, run_document_task


class CreateSessionRequest(BaseModel):
    workspace_path: str | None = None
    model: str | None = None
    title: str = "New Session"


class CreateRunRequest(BaseModel):
    prompt: str
    workspace_path: str | None = None
    document_paths: list[str] = Field(default_factory=list)
    output_path: str | None = None


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or load_config()
    app = FastAPI(title="easy-claw", version="0.1.0")

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "message": (
                "easy-claw API is running. This is a developer endpoint — "
                "use 'uv run easy-claw chat --interactive' in your terminal "
                "to start the AI assistant."
            ),
            "docs": "/docs",
            "health": "/health",
        }

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

    @app.post("/runs")
    def create_run(request: CreateRunRequest) -> dict[str, object]:
        if not request.prompt.strip() or not request.document_paths:
            raise HTTPException(
                status_code=400,
                detail="prompt and document_paths are required",
            )
        if app_config.model is None:
            raise HTTPException(status_code=400, detail="EASY_CLAW_MODEL is required")

        workspace_path = (
            Path(request.workspace_path)
            if request.workspace_path
            else app_config.default_workspace
        )
        try:
            result = run_document_task(
                config=app_config,
                prompt=request.prompt,
                document_paths=request.document_paths,
                workspace_path=workspace_path,
                output_path=request.output_path,
                title=request.prompt[:60] or "Run",
            )
        except NoReadableDocumentsError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "No readable documents found",
                    "document_errors": [
                        error.__dict__ for error in exc.load_result.errors
                    ],
                },
            ) from exc

        return {
            "session_id": result.session_id,
            "thread_id": result.thread_id,
            "content": result.content,
            "output_path": result.output_path,
            "document_errors": result.document_errors,
            "outside_workspace_paths": result.outside_workspace_paths,
        }

    return app

app = create_app()

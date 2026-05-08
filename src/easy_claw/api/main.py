from __future__ import annotations

import asyncio
import json
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
from easy_claw.cli_slash import get_slash_command_specs
from easy_claw.config import AppConfig, load_config
from easy_claw.skills import resolve_skill_sources
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import SessionRepository
from easy_claw.tools.browser import _check_playwright_browsers

_STATIC_DIR = Path(__file__).resolve().parent / "static"


class CreateSessionRequest(BaseModel):
    workspace_path: str | None = None
    model: str | None = None
    title: str = "新会话"


def _session_to_dict(session: object) -> dict[str, str | None]:
    return session.__dict__


def _resolve_session_by_prefix(repo: SessionRepository, session_id: str) -> object | None:
    exact = repo.get_session(session_id)
    if exact is not None:
        return exact
    matches = [session for session in repo.list_sessions() if session.id.startswith(session_id)]
    return matches[0] if len(matches) == 1 else None


def _count_mcp_servers(config: AppConfig) -> int:
    config_path = Path(config.mcp_config_path)
    if not config_path.is_absolute():
        config_path = config.cwd / config_path
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    return sum(
        1
        for name, server_config in data.items()
        if not str(name).startswith("_") and isinstance(server_config, dict)
    )


def _mcp_status(config: AppConfig, server_count: int) -> str:
    if config.mcp_mode == "auto":
        return f"auto（{server_count} 个服务）" if server_count else "auto"
    if config.mcp_mode == "enabled" or config.mcp_enabled:
        return f"已启用（{server_count} 个服务）" if server_count else "已启用"
    return "已关闭"


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

    @app.get("/slash-commands")
    def slash_commands() -> list[dict[str, object]]:
        return [command.__dict__ for command in get_slash_command_specs()]

    @app.get("/skills")
    def list_skill_sources() -> dict[str, object]:
        sources = resolve_skill_sources(
            app_root=app_config.cwd,
            workspace_root=app_config.default_workspace,
        )
        return {
            "sources": [
                {
                    "scope": source.scope,
                    "label": source.label,
                    "skill_count": source.skill_count,
                    "backend_path": source.backend_path,
                    "filesystem_path": str(source.filesystem_path),
                }
                for source in sources
            ],
            "source_count": len(sources),
            "skill_count": sum(source.skill_count for source in sources),
        }

    @app.get("/mcp")
    def mcp_details() -> dict[str, object]:
        server_count = _count_mcp_servers(app_config)
        return {
            "mode": app_config.mcp_mode,
            "enabled": app_config.mcp_enabled,
            "config_path": app_config.mcp_config_path,
            "server_count": server_count,
            "status": _mcp_status(app_config, server_count),
        }

    @app.get("/browser")
    def browser_details() -> dict[str, object]:
        return {
            "enabled": app_config.browser_enabled,
            "headless": app_config.browser_headless,
            "chromium_installed": _check_playwright_browsers(headless=False),
            "chromium_headless_installed": _check_playwright_browsers(headless=True),
        }

    @app.get("/sessions")
    def list_sessions() -> list[dict[str, str | None]]:
        initialize_product_db(app_config.product_db_path)
        repo = SessionRepository(app_config.product_db_path)
        return [_session_to_dict(session) for session in repo.list_sessions()]

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

    @app.get("/sessions/resolve/{session_id}")
    def resolve_session(session_id: str) -> dict[str, str | None]:
        initialize_product_db(app_config.product_db_path)
        repo = SessionRepository(app_config.product_db_path)
        session = _resolve_session_by_prefix(repo, session_id)
        if session is not None:
            return _session_to_dict(session)
        raise HTTPException(status_code=404, detail="未找到唯一匹配会话")

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, str | None]:
        initialize_product_db(app_config.product_db_path)
        repo = SessionRepository(app_config.product_db_path)
        session = repo.get_session(session_id)
        if session is not None:
            return _session_to_dict(session)
        raise HTTPException(status_code=404, detail="未找到会话")

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket) -> None:
        await websocket.accept()

        config = app_config or load_config()
        initialize_product_db(config.product_db_path)

        session_repo = SessionRepository(config.product_db_path)
        requested_session_id = websocket.query_params.get("session_id")
        session = (
            _resolve_session_by_prefix(session_repo, requested_session_id)
            if requested_session_id
            else None
        )
        if session is None:
            session = session_repo.create_session(
                workspace_path=str(config.default_workspace),
                model=config.model,
                title="网页聊天",
            )

        skill_source_records = resolve_skill_sources(
            app_root=config.cwd,
            workspace_root=config.default_workspace,
        )
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
                skill_source_records=skill_source_records,
            )
        )

        try:
            while True:
                text = await websocket.receive_text()
                if not text.strip():
                    continue

                # 同步流迭代器放到线程里运行，避免等待模型 token 时阻塞
                # asyncio 事件循环。事件产出后再转发给 WebSocket。
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

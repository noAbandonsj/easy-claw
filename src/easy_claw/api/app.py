from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from easy_claw import __version__ as _easy_claw_version
from easy_claw.agent.approvals import WebApprovalReviewer
from easy_claw.agent.langchain_runtime import AgentRequest, LangChainAgentRuntime
from easy_claw.api.schemas import (
    CreateSessionRequest,
    ResolveWorkspaceRequest,
    SaveConversationRequest,
    WebConversationMessage,
)
from easy_claw.api.websocket import event_to_dict as _event_to_dict
from easy_claw.api.websocket import next_stream_event_or_none as _next_stream_event_or_none
from easy_claw.api.websocket import parse_client_message as _parse_client_message
from easy_claw.cli.slash import get_slash_command_specs
from easy_claw.cli.views import _delete_checkpoint_thread, _write_conversation_markdown
from easy_claw.config import AppConfig, load_config
from easy_claw.skills import resolve_skill_sources
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import SessionRepository
from easy_claw.tools.browser import _check_playwright_browsers


def _react_dist_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def _react_index_response() -> FileResponse:
    index_path = _react_dist_dir() / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="React web UI has not been built")
    return FileResponse(index_path)


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


def _browser_payload(config: AppConfig) -> dict[str, object]:
    return {
        "enabled": config.browser_enabled,
        "headless": config.browser_headless,
        "chromium_installed": _check_playwright_browsers(headless=False),
        "chromium_headless_installed": _check_playwright_browsers(headless=True),
    }


def _doctor_payload(config: AppConfig) -> dict[str, object]:
    server_count = _count_mcp_servers(config)
    return {
        "version": _easy_claw_version,
        "data_dir": str(config.data_dir),
        "product_db_path": str(config.product_db_path),
        "checkpoint_db_path": str(config.checkpoint_db_path),
        "workspace": str(config.default_workspace),
        "model": config.model,
        "base_url": config.base_url,
        "api_key_configured": config.api_key is not None,
        "approval_mode": config.approval_mode,
        "execution_mode": config.execution_mode,
        "mcp_mode": config.mcp_mode,
        "mcp_config_path": config.mcp_config_path,
        "mcp_status": _mcp_status(config, server_count),
        "mcp_server_count": server_count,
        "max_model_calls": config.max_model_calls,
        "max_tool_calls": config.max_tool_calls,
        "browser": _browser_payload(config),
    }


def _resolve_workspace_path(path: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="不是目录")
    return resolved


def _config_for_web_session(
    config: AppConfig,
    session: object,
    *,
    workspace_path: str | None,
    model: str | None,
) -> AppConfig:
    resolved_workspace: Path | None = None
    if workspace_path:
        resolved_workspace = _resolve_workspace_path(workspace_path)
    else:
        session_workspace = getattr(session, "workspace_path", None)
        if session_workspace:
            candidate = Path(str(session_workspace)).expanduser()
            if candidate.is_dir():
                resolved_workspace = candidate.resolve()

    resolved_model = model.strip() if model and model.strip() else None
    if resolved_model is None:
        session_model = getattr(session, "model", None)
        resolved_model = str(session_model) if session_model else config.model

    return replace(
        config,
        default_workspace=resolved_workspace or config.default_workspace,
        model=resolved_model,
    )


def _web_messages_to_conversation(
    messages: list[WebConversationMessage],
) -> list[tuple[str, str]]:
    conversation: list[tuple[str, str]] = []
    pending_user: str | None = None
    for message in messages:
        content = message.content or ""
        if message.kind == "user":
            if pending_user is not None:
                conversation.append((pending_user, ""))
            pending_user = content
        elif message.kind == "assistant":
            conversation.append((pending_user or "", content))
            pending_user = None
    if pending_user is not None:
        conversation.append((pending_user, ""))
    return conversation


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or load_config()
    app = FastAPI(title="easy-claw", version="0.5.0")

    @app.get("/")
    def root() -> FileResponse:
        return _react_index_response()

    react_dist = _react_dist_dir()
    react_assets = react_dist / "assets"
    if react_assets.exists():
        app.mount(
            "/app/assets",
            StaticFiles(directory=react_assets),
            name="react-assets",
        )

    @app.get("/app")
    @app.get("/app/{path:path}")
    def react_app(path: str = "") -> FileResponse:
        return _react_index_response()

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
        return _browser_payload(app_config)

    @app.get("/doctor")
    def doctor_details() -> dict[str, object]:
        return _doctor_payload(app_config)

    @app.post("/workspace/resolve")
    def resolve_workspace(request: ResolveWorkspaceRequest) -> dict[str, str]:
        return {"workspace_path": str(_resolve_workspace_path(request.path))}

    @app.post("/conversation/save")
    def save_conversation(request: SaveConversationRequest) -> dict[str, object]:
        export_config = replace(
            app_config,
            default_workspace=(
                Path(request.workspace_path).expanduser().resolve()
                if request.workspace_path
                else app_config.default_workspace
            ),
            model=request.model or app_config.model,
        )
        save_path = Path(request.path).expanduser().resolve()
        _write_conversation_markdown(
            _web_messages_to_conversation(request.messages),
            save_path,
            request.session_id,
            export_config,
        )
        return {"saved": True, "path": str(save_path)}

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

    @app.delete("/sessions/{session_id}")
    def delete_session(session_id: str) -> dict[str, object]:
        initialize_product_db(app_config.product_db_path)
        repo = SessionRepository(app_config.product_db_path)
        session = _resolve_session_by_prefix(repo, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="未找到唯一匹配会话")
        repo.delete_session(session.id)
        _delete_checkpoint_thread(session.id, app_config.checkpoint_db_path)
        return {"deleted": True, "session": _session_to_dict(session)}

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket) -> None:
        await websocket.accept()

        config = app_config or load_config()
        initialize_product_db(config.product_db_path)

        session_repo = SessionRepository(config.product_db_path)
        requested_session_id = websocket.query_params.get("session_id")
        requested_workspace = websocket.query_params.get("workspace_path")
        requested_model = websocket.query_params.get("model")
        session = (
            _resolve_session_by_prefix(session_repo, requested_session_id)
            if requested_session_id
            else None
        )
        if session is None:
            initial_config = replace(
                config,
                default_workspace=(
                    _resolve_workspace_path(requested_workspace)
                    if requested_workspace
                    else config.default_workspace
                ),
                model=(
                    requested_model.strip()
                    if requested_model and requested_model.strip()
                    else config.model
                ),
            )
            session = session_repo.create_session(
                workspace_path=str(initial_config.default_workspace),
                model=initial_config.model,
                title="网页聊天",
            )

        try:
            session_config = _config_for_web_session(
                config,
                session,
                workspace_path=requested_workspace,
                model=requested_model,
            )
        except HTTPException as exc:
            await websocket.send_json({"type": "error", "content": exc.detail})
            return

        skill_source_records = resolve_skill_sources(
            app_root=session_config.cwd,
            workspace_root=session_config.default_workspace,
        )
        reviewer = WebApprovalReviewer()
        runtime = LangChainAgentRuntime(reviewer=reviewer)

        await websocket.send_json(
            {
                "type": "banner",
                "model": session_config.model,
                "workspace": str(session_config.default_workspace),
                "version": _easy_claw_version,
                "session_id": session.id[:8],
            }
        )

        try:
            agent_session = runtime.open_session(
                AgentRequest(
                    prompt="",
                    thread_id=session.id,
                    config=session_config,
                    skill_source_records=skill_source_records,
                )
            )
        except RuntimeError as exc:
            await websocket.send_json({"type": "error", "content": str(exc)})
            return

        try:
            while True:
                raw_message = await websocket.receive_text()
                payload = _parse_client_message(raw_message)
                if payload.get("type") != "prompt":
                    continue
                text = str(payload.get("content") or "")
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
                    if event.type == "approval_required":
                        while True:
                            decision_raw = await websocket.receive_text()
                            decision = _parse_client_message(decision_raw)
                            if decision.get("type") != "approval_decision":
                                await websocket.send_json(
                                    {
                                        "type": "error",
                                        "content": "请先处理当前审批请求。",
                                    }
                                )
                                continue
                            try:
                                reviewer.submit(
                                    str(decision.get("approval_id") or ""),
                                    approve=bool(decision.get("approve")),
                                    message=(
                                        str(decision.get("message"))
                                        if decision.get("message")
                                        else None
                                    ),
                                )
                            except ValueError as exc:
                                await websocket.send_json(
                                    {"type": "error", "content": str(exc)}
                                )
                                continue
                            break
        except WebSocketDisconnect:
            pass
        finally:
            agent_session.close()

    return app


app = create_app()

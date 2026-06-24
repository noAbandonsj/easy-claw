from __future__ import annotations

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    workspace_path: str | None = None
    model: str | None = None
    title: str = "新会话"


class ResolveWorkspaceRequest(BaseModel):
    path: str


class WebConversationMessage(BaseModel):
    kind: str
    content: str | None = None
    name: str | None = None
    result: object | None = None


class SaveConversationRequest(BaseModel):
    path: str
    session_id: str
    messages: list[WebConversationMessage]
    workspace_path: str | None = None
    model: str | None = None

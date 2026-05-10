from __future__ import annotations

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    workspace_path: str | None = None
    model: str | None = None
    title: str = "新会话"

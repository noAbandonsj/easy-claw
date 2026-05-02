from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from easy_claw.storage.db import connect_product_db


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class SessionRecord:
    id: str
    title: str
    workspace_path: str
    model: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MemoryItem:
    id: str
    scope: str
    key: str
    content: str
    source: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AuditLog:
    id: str
    event_type: str
    payload_json: str
    created_at: str


class SessionRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def create_session(
        self,
        *,
        workspace_path: str,
        model: str | None,
        title: str = "New Session",
    ) -> SessionRecord:
        timestamp = _now()
        record = SessionRecord(
            id=str(uuid4()),
            title=title,
            workspace_path=workspace_path,
            model=model,
            created_at=timestamp,
            updated_at=timestamp,
        )
        with connect_product_db(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, title, workspace_path, model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.title,
                    record.workspace_path,
                    record.model,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def list_sessions(self) -> list[SessionRecord]:
        with connect_product_db(self._db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, title, workspace_path, model, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [SessionRecord(**dict(row)) for row in rows]

    def get_session(self, session_id: str) -> SessionRecord | None:
        with connect_product_db(self._db_path) as connection:
            row = connection.execute(
                """
                SELECT id, title, workspace_path, model, created_at, updated_at
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return SessionRecord(**dict(row))


class MemoryRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def remember(
        self,
        *,
        scope: str,
        key: str,
        content: str,
        source: str = "user",
    ) -> MemoryItem:
        timestamp = _now()
        record = MemoryItem(
            id=str(uuid4()),
            scope=scope,
            key=key,
            content=content,
            source=source,
            created_at=timestamp,
            updated_at=timestamp,
        )
        with connect_product_db(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO memory_items (id, scope, key, content, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.scope,
                    record.key,
                    record.content,
                    record.source,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def list_memory(self) -> list[MemoryItem]:
        with connect_product_db(self._db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, scope, key, content, source, created_at, updated_at
                FROM memory_items
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [MemoryItem(**dict(row)) for row in rows]


class AuditRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def record(self, *, event_type: str, payload: dict[str, object]) -> AuditLog:
        record = AuditLog(
            id=str(uuid4()),
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            created_at=_now(),
        )
        with connect_product_db(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO audit_logs (id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (record.id, record.event_type, record.payload_json, record.created_at),
            )
        return record

    def list_logs(self) -> list[AuditLog]:
        with connect_product_db(self._db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, event_type, payload_json, created_at
                FROM audit_logs
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [AuditLog(**dict(row)) for row in rows]

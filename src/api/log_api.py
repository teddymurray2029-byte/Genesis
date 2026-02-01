from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DEFAULT_DB_PATH = os.getenv("GENESIS_LOG_DB", "genesis_logs.sqlite3")


@dataclass(frozen=True)
class LogRecord:
    id: int
    payload: Dict[str, Any]
    created_at: str
    updated_at: str


class LogCreate(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class LogUpdate(BaseModel):
    payload: Dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        yield connection
    finally:
        connection.close()


def _init_db(db_path: str) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_id ON logs (id)"
        )
        connection.commit()


def _row_to_record(row: sqlite3.Row) -> LogRecord:
    return LogRecord(
        id=row["id"],
        payload=_deserialize_payload(row["payload"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _serialize_payload(payload: Dict[str, Any]) -> str:
    import json

    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _deserialize_payload(payload: str) -> Dict[str, Any]:
    import json

    return json.loads(payload)


def _fetch_log(db_path: str, log_id: int) -> Optional[LogRecord]:
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT id, payload, created_at, updated_at FROM logs WHERE id = ?",
            (log_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_record(row)


def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    _init_db(db_path)

    app = FastAPI(title="Genesis Log API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/logs", response_model=LogRecord)
    def create_log(body: LogCreate) -> LogRecord:
        timestamp = _utc_now()
        payload_text = _serialize_payload(body.payload)
        with _connect(db_path) as connection:
            cursor = connection.execute(
                "INSERT INTO logs (payload, created_at, updated_at) VALUES (?, ?, ?)",
                (payload_text, timestamp, timestamp),
            )
            connection.commit()
            log_id = cursor.lastrowid
        record = _fetch_log(db_path, int(log_id))
        if record is None:
            raise HTTPException(status_code=500, detail="Log insert failed")
        return record

    @app.get("/logs/{log_id}", response_model=LogRecord)
    def read_log(log_id: int) -> LogRecord:
        record = _fetch_log(db_path, log_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Log not found")
        return record

    @app.put("/logs/{log_id}", response_model=LogRecord)
    def update_log(log_id: int, body: LogUpdate) -> LogRecord:
        payload_text = _serialize_payload(body.payload)
        timestamp = _utc_now()
        with _connect(db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE logs
                SET payload = ?, updated_at = ?
                WHERE id = ?
                """,
                (payload_text, timestamp, log_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Log not found")
        record = _fetch_log(db_path, log_id)
        if record is None:
            raise HTTPException(status_code=500, detail="Log update failed")
        return record

    @app.delete("/logs/{log_id}")
    def delete_log(log_id: int) -> Dict[str, Any]:
        with _connect(db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM logs WHERE id = ?",
                (log_id,),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Log not found")
        return {"deleted": True, "id": log_id}

    return app


app = create_app()

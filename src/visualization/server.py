"""FastAPI service for the Genesis visualization UI."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from src.db.log_store import LogStore, QueryResult, resolve_log_db_path

app = FastAPI(title="Genesis Visualization Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


DEFAULT_DB_PATH = os.getenv("GENESIS_DB_PATH", "data/genesis_db.json")


class LogEntry(BaseModel):
    id: int
    message: str | None = None
    level: str | None = None


class LogCreate(BaseModel):
    message: str
    level: str = "info"


class LogUpdate(BaseModel):
    message: str | None = None
    level: str | None = None


def _sql_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _run_log_query(sql: str) -> QueryResult:
    try:
        return LOG_STORE.execute_sql(sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _fetch_log(log_id: int) -> LogEntry | None:
    result = _run_log_query(f"SELECT * FROM logs WHERE id = {log_id} LIMIT 1")
    if not result.rows:
        return None
    return LogEntry(**result.rows[0])


LOG_STORE = LogStore(db_path=resolve_log_db_path(DEFAULT_DB_PATH))


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        to_remove: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(payload)
            except Exception:
                to_remove.append(connection)
        for connection in to_remove:
            self._connections.discard(connection)

    async def send(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            self.disconnect(websocket)


_CONNECTIONS = ConnectionManager()


def _schedule_broadcast(event_type: str, payload: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_CONNECTIONS.broadcast({"type": "event", "event_type": event_type, "data": payload}))


LOG_STORE = LogStore(LOG_STORE_PATH, LOG_LOCK_PATH, event_emitter=_schedule_broadcast)


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def build_initial_state() -> dict[str, Any]:
    return {
        "type": "initial_state",
        "brain_space": {"clusters": []},
        "controls": {"streaming": False},
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await _CONNECTIONS.connect(websocket)
    await websocket.send_json(build_initial_state())
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=15)
                await websocket.send_json({"type": "ack", "message": message})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        _CONNECTIONS.disconnect(websocket)
        return


@app.get("/logs")
@app.get("/api/logs")
def list_logs(
    log_type: str | None = Query(default=None, alias="type"),
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[LogEntry]:
    if start is not None or end is not None:
        raise HTTPException(status_code=400, detail="Timestamp filtering is not supported by the log store")
    where_clause = f" WHERE level = {_sql_literal(log_type)}" if log_type else ""
    result = _run_log_query(f"SELECT * FROM logs{where_clause} ORDER BY id DESC")
    return [LogEntry(**row) for row in result.rows]


@app.post("/logs")
@app.post("/api/logs")
async def create_log(payload: LogCreate) -> LogEntry:
    _run_log_query(
        "INSERT INTO logs (message, level) "
        f"VALUES ({_sql_literal(payload.message)}, {_sql_literal(payload.level)})"
    )
    result = _run_log_query("SELECT * FROM logs ORDER BY id DESC LIMIT 1")
    if not result.rows:
        raise HTTPException(status_code=500, detail="Failed to load created log entry")
    entry = LogEntry(**result.rows[0])
    await _CONNECTIONS.broadcast(
        {
            "type": "event",
            "event": {
                "type": "log",
                "log_type": entry.type,
                "message": entry.message,
                "timestamp": entry.timestamp.isoformat(),
                "log_type": entry.type,
                "payload": entry.payload,
                "tags": entry.tags,
            },
        }
    )
    return entry


@app.get("/logs/{log_id}")
@app.get("/api/logs/{log_id}")
def get_log(log_id: int) -> LogEntry:
    entry = _fetch_log(log_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    return entry


@app.put("/logs/{log_id}")
@app.put("/api/logs/{log_id}")
@app.patch("/logs/{log_id}")
@app.patch("/api/logs/{log_id}")
def update_log(log_id: int, payload: LogUpdate) -> LogEntry:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    assignments = ", ".join(f"{column} = {_sql_literal(value)}" for column, value in updates.items())
    result = _run_log_query(f"UPDATE logs SET {assignments} WHERE id = {log_id}")
    if result.affected_rows == 0:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    updated = _fetch_log(log_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    return updated


@app.delete("/logs/{log_id}")
@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int) -> dict[str, str]:
    result = _run_log_query(f"DELETE FROM logs WHERE id = {log_id}")
    if result.affected_rows == 0:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    return {"status": "deleted"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Genesis visualization service.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind.")
    parser.add_argument("--log-level", default="info", help="Uvicorn log level.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development only).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        "src.visualization.server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

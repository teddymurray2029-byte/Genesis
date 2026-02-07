"""FastAPI service for the Genesis visualization UI."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from fastapi import Body, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from strawberry.fastapi import GraphQLRouter
import uvicorn

from src.api.models import QueryBatchResponse, QueryResponse, SqlQuery
from src.api.sql_utils import normalize_sql_statement, parse_sql_statements
from src.db.genesis_db import GenesisDB
from src.db.log_store import LogStore, QueryResult, resolve_log_db_path
from src.visualization.graphql_schema import build_graphql_context, schema as graphql_schema

app = FastAPI(title="Genesis Visualization Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


DEFAULT_VOXEL_CLOUD_PATH = os.getenv("GENESIS_VOXEL_CLOUD_PATH")
DEFAULT_DB_PATH = os.getenv("GENESIS_DB_PATH", "data/genesis_db.json")
LOG_WS_INITIAL_LIMIT = 100


class LogEntry(BaseModel):
    id: int
    timestamp: str | None = None
    type: str | None = None
    message: str | None = None
    payload: Any | None = None
    tags: list[str] | None = None


class LogCreate(BaseModel):
    message: str
    type: str = "info"
    payload: Any | None = None
    tags: list[str] | None = None


class LogUpdate(BaseModel):
    message: str | None = None
    type: str | None = None
    payload: Any | None = None
    tags: list[str] | None = None


def _sql_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _run_log_query(sql: str) -> QueryResult:
    try:
        return LOG_STORE.execute_sql(sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _query_entries(sql: str, params: Iterable[Any]) -> QueryResponse:
    if params:
        raise HTTPException(status_code=400, detail="SQL parameters are not supported by GenesisDB")
    normalized = normalize_sql_statement(sql)
    complexity = GENESIS_DB.estimate_time_complexity(normalized)
    start = time.perf_counter()
    try:
        result = GENESIS_DB.execute_sql(normalized)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    elapsed_ms = (time.perf_counter() - start) * 1000
    return QueryResponse(
        rows=result.rows,
        row_count=len(result.rows),
        columns=result.columns,
        affected_rows=result.affected_rows,
        operation=result.operation,
        execution_time_ms=elapsed_ms,
        time_complexity=complexity,
    )


def _query_logs(sql: str, params: Iterable[Any]) -> QueryResponse:
    if params:
        raise HTTPException(status_code=400, detail="SQL parameters are not supported by the log store")
    normalized = normalize_sql_statement(sql)
    complexity = LOG_STORE.estimate_time_complexity(normalized)
    start = time.perf_counter()
    try:
        result = LOG_STORE.execute_sql(normalized)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    elapsed_ms = (time.perf_counter() - start) * 1000
    return QueryResponse(
        rows=result.rows,
        row_count=len(result.rows),
        columns=result.columns,
        affected_rows=result.affected_rows,
        operation=result.operation,
        execution_time_ms=elapsed_ms,
        time_complexity=complexity,
    )


def _targets_logs(sql: str) -> bool:
    normalized = sql.lower()
    patterns = [
        r"\bfrom\s+logs\b",
        r"\binto\s+logs\b",
        r"\bupdate\s+logs\b",
        r"\bdelete\s+from\s+logs\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def _fetch_log(log_id: int) -> LogEntry | None:
    result = _run_log_query(f"SELECT * FROM logs WHERE id = {log_id} LIMIT 1")
    if not result.rows:
        return None
    return LogEntry(**result.rows[0])


GENESIS_DB = GenesisDB(db_path=DEFAULT_DB_PATH, voxel_cloud_path=DEFAULT_VOXEL_CLOUD_PATH)
LOG_STORE = LogStore(db_path=resolve_log_db_path(DEFAULT_DB_PATH))
graphql_router = GraphQLRouter(graphql_schema, context_getter=build_graphql_context(LOG_STORE))
app.include_router(graphql_router, prefix="/graphql")


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
_LOG_CONNECTIONS = ConnectionManager()


def _schedule_broadcast(event_type: str, payload: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_CONNECTIONS.broadcast({"type": "event", "event_type": event_type, "data": payload}))


def _log_event_payload(entry: LogEntry, action: str) -> dict[str, Any]:
    return {
        "type": "log",
        "action": action,
        "id": entry.id,
        "timestamp": entry.timestamp,
        "type": entry.type,
        "message": entry.message,
        "payload": entry.payload,
        "tags": entry.tags,
    }


async def _broadcast_log_event(entry: LogEntry, action: str) -> None:
    payload = {"type": "event", "event": _log_event_payload(entry, action)}
    await _CONNECTIONS.broadcast(payload)
    await _LOG_CONNECTIONS.broadcast(payload)


def _schedule_log_broadcast(entry: LogEntry, action: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_broadcast_log_event(entry, action))


def _load_recent_logs(limit: int = LOG_WS_INITIAL_LIMIT) -> list[LogEntry]:
    result = _run_log_query(f"SELECT * FROM logs ORDER BY id DESC LIMIT {limit}")
    return [LogEntry(**row) for row in result.rows]


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse | QueryBatchResponse)
def query(request: SqlQuery | None = Body(default=None)) -> QueryResponse | QueryBatchResponse:
    if request is None or not request.sql.strip():
        raise HTTPException(status_code=400, detail="SQL query must not be empty")
    statements = parse_sql_statements(request.sql)
    if len(statements) > 1 and request.params:
        raise HTTPException(
            status_code=400,
            detail="SQL parameters are only supported for single-statement queries",
        )
    results: list[QueryResponse] = []
    start = time.perf_counter()
    for statement in statements:
        if _targets_logs(statement):
            results.append(_query_logs(statement, request.params))
        else:
            results.append(_query_entries(statement, request.params))
    total_elapsed_ms = (time.perf_counter() - start) * 1000
    if len(results) == 1:
        return results[0]
    return QueryBatchResponse(
        results=results,
        statement_count=len(results),
        execution_time_ms=total_elapsed_ms,
    )


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


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    await _LOG_CONNECTIONS.connect(websocket)
    initial_logs = _load_recent_logs()
    await websocket.send_json(
        {
            "type": "logs_initial",
            "logs": [entry.model_dump() for entry in initial_logs],
        }
    )
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=15)
                await websocket.send_json({"type": "ack", "message": message})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        _LOG_CONNECTIONS.disconnect(websocket)
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
    where_clause = f" WHERE type = {_sql_literal(log_type)}" if log_type else ""
    result = _run_log_query(f"SELECT * FROM logs{where_clause} ORDER BY id DESC")
    return [LogEntry(**row) for row in result.rows]


@app.post("/logs")
@app.post("/api/logs")
async def create_log(payload: LogCreate) -> LogEntry:
    _run_log_query(
        "INSERT INTO logs (message, type, payload, tags) "
        "VALUES ("
        f"{_sql_literal(payload.message)}, "
        f"{_sql_literal(payload.type)}, "
        f"{_sql_literal(payload.payload)}, "
        f"{_sql_literal(payload.tags)}"
        ")"
    )
    result = _run_log_query("SELECT * FROM logs ORDER BY id DESC LIMIT 1")
    if not result.rows:
        raise HTTPException(status_code=500, detail="Failed to load created log entry")
    entry = LogEntry(**result.rows[0])
    await _broadcast_log_event(entry, "created")
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
    _schedule_log_broadcast(updated, "updated")
    return updated


@app.delete("/logs/{log_id}")
@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int) -> dict[str, str]:
    existing = _fetch_log(log_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    result = _run_log_query(f"DELETE FROM logs WHERE id = {log_id}")
    if result.affected_rows == 0:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    _schedule_log_broadcast(existing, "deleted")
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

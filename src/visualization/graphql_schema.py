"""GraphQL schema for the Genesis visualization service."""

from __future__ import annotations

import json
from typing import Any, Callable

from fastapi import HTTPException
import strawberry
from strawberry.scalars import JSON
from strawberry.types import Info

from src.api.sql_utils import normalize_sql
from src.db.log_store import LogStore, QueryResult as LogQueryResult


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


def _execute_log_sql(log_store: LogStore, sql: str) -> LogQueryResult:
    try:
        return log_store.execute_sql(sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _fetch_log_row(log_store: LogStore, log_id: int) -> dict[str, Any] | None:
    result = _execute_log_sql(log_store, f"SELECT * FROM logs WHERE id = {log_id} LIMIT 1")
    if not result.rows:
        return None
    return result.rows[0]


def _query_logs(log_store: LogStore, sql: str) -> "QueryResult":
    normalized = normalize_sql(sql)
    complexity = log_store.estimate_time_complexity(normalized)
    result = _execute_log_sql(log_store, normalized)
    return QueryResult(
        rows=result.rows,
        row_count=len(result.rows),
        columns=result.columns,
        affected_rows=result.affected_rows,
        operation=result.operation,
        time_complexity=complexity,
    )


@strawberry.type
class LogEntry:
    id: int
    timestamp: str | None
    type: str | None
    message: str | None
    payload: JSON | None
    tags: list[str] | None


@strawberry.type
class QueryResult:
    rows: list[JSON]
    row_count: int
    columns: list[str]
    affected_rows: int
    operation: str
    time_complexity: str | None


@strawberry.type
class Query:
    @strawberry.field
    def log(self, info: Info, log_id: int) -> LogEntry | None:
        log_store: LogStore = info.context["log_store"]
        row = _fetch_log_row(log_store, log_id)
        if row is None:
            return None
        return LogEntry(**row)

    @strawberry.field
    def logs(self, info: Info, log_type: str | None = None) -> list[LogEntry]:
        log_store: LogStore = info.context["log_store"]
        where_clause = f" WHERE type = {_sql_literal(log_type)}" if log_type else ""
        result = _execute_log_sql(log_store, f"SELECT * FROM logs{where_clause} ORDER BY id DESC")
        return [LogEntry(**row) for row in result.rows]

    @strawberry.field(name="query")
    def query_logs(self, info: Info, sql: str) -> QueryResult:
        log_store: LogStore = info.context["log_store"]
        return _query_logs(log_store, sql)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_log(
        self,
        info: Info,
        message: str,
        type: str = "info",
        payload: JSON | None = None,
        tags: list[str] | None = None,
    ) -> LogEntry:
        log_store: LogStore = info.context["log_store"]
        _execute_log_sql(
            log_store,
            "INSERT INTO logs (message, type, payload, tags) "
            "VALUES ("
            f"{_sql_literal(message)}, "
            f"{_sql_literal(type)}, "
            f"{_sql_literal(payload)}, "
            f"{_sql_literal(tags)}"
            ")",
        )
        result = _execute_log_sql(log_store, "SELECT * FROM logs ORDER BY id DESC LIMIT 1")
        if not result.rows:
            raise HTTPException(status_code=500, detail="Failed to load created log entry")
        return LogEntry(**result.rows[0])

    @strawberry.mutation
    def update_log(
        self,
        info: Info,
        log_id: int,
        message: str | None = None,
        type: str | None = None,
        payload: JSON | None = None,
        tags: list[str] | None = None,
    ) -> LogEntry:
        log_store: LogStore = info.context["log_store"]
        updates = {
            "message": message,
            "type": type,
            "payload": payload,
            "tags": tags,
        }
        updates = {key: value for key, value in updates.items() if value is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        assignments = ", ".join(f"{column} = {_sql_literal(value)}" for column, value in updates.items())
        result = _execute_log_sql(log_store, f"UPDATE logs SET {assignments} WHERE id = {log_id}")
        if result.affected_rows == 0:
            raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
        row = _fetch_log_row(log_store, log_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
        return LogEntry(**row)

    @strawberry.mutation
    def delete_log(self, info: Info, log_id: int) -> bool:
        log_store: LogStore = info.context["log_store"]
        result = _execute_log_sql(log_store, f"DELETE FROM logs WHERE id = {log_id}")
        if result.affected_rows == 0:
            raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
        return True


schema = strawberry.Schema(query=Query, mutation=Mutation)


def build_graphql_context(log_store: LogStore) -> Callable[[], dict[str, Any]]:
    def _context() -> dict[str, Any]:
        return {"log_store": log_store}

    return _context

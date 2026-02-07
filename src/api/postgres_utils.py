from __future__ import annotations

import os
import time
from typing import Any, Iterable

import psycopg2
from fastapi import HTTPException

from src.api.models import PostgresQueryResponse
from src.api.sql_utils import get_query_type, normalize_sql_statement


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured")
    return database_url


def execute_postgres_statement(sql: str, params: Iterable[Any]) -> PostgresQueryResponse:
    normalized = normalize_sql_statement(sql)
    start = time.perf_counter()
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(_get_database_url())
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute(normalized, list(params) if params else None)
        query_type = get_query_type(normalized)
        rows: list[dict[str, Any]] = []
        columns: list[str] = []
        if cursor.description:
            columns = [description[0] for description in cursor.description]
            fetched = cursor.fetchall()
            rows = [dict(zip(columns, row)) for row in fetched]
        affected_rows = cursor.rowcount if cursor.rowcount is not None else 0
        if affected_rows == -1:
            affected_rows = len(rows)
        conn.commit()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return PostgresQueryResponse(
            rows=rows,
            columns=columns,
            query_type=query_type,
            message=cursor.statusmessage or "",
            affected_rows=affected_rows,
            execution_time_ms=elapsed_ms,
        )
    except psycopg2.Error as exc:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=400, detail=f"PostgreSQL Error: {exc}") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

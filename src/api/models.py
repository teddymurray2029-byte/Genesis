from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SqlQuery(BaseModel):
    sql: str = Field(..., description="SQL query targeting the entries table.")
    params: list[Any] = Field(default_factory=list, description="SQL parameters for placeholders.")


class QueryResponse(BaseModel):
    rows: list[dict[str, Any]]
    row_count: int
    columns: list[str] = Field(default_factory=list)
    affected_rows: int = 0
    operation: str = "select"
    query_type: str = "select"
    message: str = ""
    execution_time_ms: float = 0.0
    time_complexity: str | None = None


class QueryBatchResponse(BaseModel):
    results: list[QueryResponse]
    statement_count: int
    total_row_count: int = 0
    total_affected_rows: int = 0
    execution_time_ms: float = 0.0

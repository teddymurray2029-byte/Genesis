from __future__ import annotations

import os
import re
from typing import Any, Iterable, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.sql_utils import normalize_sql
from src.db.genesis_db import GenesisDB
from src.db.log_store import LogStore, resolve_log_db_path

DEFAULT_VOXEL_CLOUD_PATH = os.getenv("GENESIS_VOXEL_CLOUD_PATH")
DEFAULT_DB_PATH = os.getenv("GENESIS_DB_PATH", "data/genesis_db.json")


class SqlQuery(BaseModel):
    sql: str = Field(..., description="SQL query targeting the entries table.")
    params: list[Any] = Field(default_factory=list, description="SQL parameters for placeholders.")


class QueryResponse(BaseModel):
    rows: list[dict[str, Any]]
    row_count: int
    columns: list[str] = Field(default_factory=list)
    affected_rows: int = 0
    operation: str = "select"


class ReloadRequest(BaseModel):
    voxel_cloud_path: Optional[str] = Field(
        default=None,
        description="Optional path to a serialized VoxelCloud pickle.",
    )
    db_path: Optional[str] = Field(
        default=None,
        description="Optional path to the GenesisDB JSON file.",
    )


def _load_db(db_path: str, voxel_cloud_path: Optional[str]) -> GenesisDB:
    return GenesisDB(db_path=db_path, voxel_cloud_path=voxel_cloud_path)


def _load_log_store(db_path: str) -> LogStore:
    return LogStore(db_path=resolve_log_db_path(db_path))


def _query_entries(db: GenesisDB, sql: str, params: Iterable[Any]) -> QueryResponse:
    if params:
        raise HTTPException(status_code=400, detail="SQL parameters are not supported by GenesisDB")
    try:
        result = db.execute_sql(sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryResponse(
        rows=result.rows,
        row_count=len(result.rows),
        columns=result.columns,
        affected_rows=result.affected_rows,
        operation=result.operation,
    )


def _query_logs(log_store: LogStore, sql: str, params: Iterable[Any]) -> QueryResponse:
    if params:
        raise HTTPException(status_code=400, detail="SQL parameters are not supported by the log store")
    try:
        result = log_store.execute_sql(sql)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryResponse(
        rows=result.rows,
        row_count=len(result.rows),
        columns=result.columns,
        affected_rows=result.affected_rows,
        operation=result.operation,
    )


def _targets_logs(sql: str) -> bool:
    normalized = sql.lower()
    patterns = [
        r"\\bfrom\\s+logs\\b",
        r"\\binto\\s+logs\\b",
        r"\\bupdate\\s+logs\\b",
        r"\\bdelete\\s+from\\s+logs\\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def create_app(
    voxel_cloud_path: Optional[str] = DEFAULT_VOXEL_CLOUD_PATH,
    db_path: str = DEFAULT_DB_PATH,
) -> FastAPI:
    db = _load_db(db_path, voxel_cloud_path)
    log_store = _load_log_store(db_path)

    app = FastAPI(title="Genesis SQL API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check() -> dict[str, Any]:
        return {
            "status": "ok",
            "entries": db.entry_count,
            "voxel_cloud_path": voxel_cloud_path,
            "db_path": db_path,
        }

    @app.get("/schema")
    def schema() -> dict[str, Any]:
        return {
            "entries": {"table": "entries", "columns": db.schema},
            "logs": {"table": "logs", "columns": log_store.schema},
        }

    @app.post("/query", response_model=QueryResponse)
    def query_entries(request: SqlQuery) -> QueryResponse:
        sql = normalize_sql(request.sql)
        if _targets_logs(sql):
            return _query_logs(log_store, sql, request.params)
        return _query_entries(db, sql, request.params)

    @app.post("/reload")
    def reload_cloud(request: ReloadRequest) -> dict[str, Any]:
        nonlocal db, voxel_cloud_path, db_path, log_store
        voxel_cloud_path = request.voxel_cloud_path or voxel_cloud_path
        db_path = request.db_path or db_path
        if not db_path:
            raise HTTPException(status_code=400, detail="GenesisDB path is required")
        db = _load_db(db_path, voxel_cloud_path)
        log_store = _load_log_store(db_path)
        return {
            "status": "ok",
            "voxel_cloud_path": voxel_cloud_path,
            "db_path": db_path,
            "entries": db.entry_count,
        }

    return app


app = create_app()

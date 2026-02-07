from __future__ import annotations

import os
import time
from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.models import PostgresQuery, PostgresQueryBatchResponse, PostgresQueryResponse
from src.api.postgres_utils import execute_postgres_statement
from src.api.sql_utils import parse_sql_statements
from src.db.genesis_db import GenesisDB
from src.db.log_store import LogStore, resolve_log_db_path

DEFAULT_VOXEL_CLOUD_PATH = os.getenv("GENESIS_VOXEL_CLOUD_PATH")
DEFAULT_DB_PATH = os.getenv("GENESIS_DB_PATH", "data/genesis_db.json")


class SchemaColumn(BaseModel):
    name: str
    type: str


class SchemaUpdate(BaseModel):
    columns: Optional[list[SchemaColumn]] = Field(
        default=None,
        description="Optional list of schema columns (read-only for GenesisDB).",
    )
    constraints: Optional[list[str]] = Field(
        default=None,
        description="Optional list of constraints metadata strings.",
    )
    indexes: Optional[list[str]] = Field(
        default=None,
        description="Optional list of index metadata strings.",
    )


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


def create_app(
    voxel_cloud_path: Optional[str] = DEFAULT_VOXEL_CLOUD_PATH,
    db_path: str = DEFAULT_DB_PATH,
) -> FastAPI:
    db = _load_db(db_path, voxel_cloud_path)
    log_store = _load_log_store(db_path)
    schema_constraints: list[str] = []
    schema_indexes: list[str] = []

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
            "table": "entries",
            "columns": db.schema,
            "constraints": schema_constraints,
            "indexes": schema_indexes,
        }

    @app.post("/schema")
    def update_schema(request: SchemaUpdate) -> dict[str, Any]:
        nonlocal schema_constraints, schema_indexes
        if request.columns is not None:
            expected = [{"name": column["name"], "type": column["type"]} for column in db.schema]
            provided = [{"name": column.name, "type": column.type} for column in request.columns]
            if provided != expected:
                raise HTTPException(
                    status_code=400,
                    detail="GenesisDB schema columns are fixed and cannot be modified.",
                )
        if request.constraints is not None:
            schema_constraints = request.constraints
        if request.indexes is not None:
            schema_indexes = request.indexes
        return {
            "table": "entries",
            "columns": db.schema,
            "constraints": schema_constraints,
            "indexes": schema_indexes,
        }

    @app.post("/query", response_model=PostgresQueryResponse | PostgresQueryBatchResponse)
    def query_entries(
        request: PostgresQuery | None = Body(default=None),
    ) -> PostgresQueryResponse | PostgresQueryBatchResponse:
        if request is None or not request.sql.strip():
            raise HTTPException(status_code=400, detail="SQL query must not be empty")
        statements = parse_sql_statements(request.sql)
        if len(statements) > 1 and request.params:
            raise HTTPException(
                status_code=400,
                detail="SQL parameters are only supported for single-statement queries",
            )
        results: list[PostgresQueryResponse] = []
        start = time.perf_counter()
        for statement in statements:
            results.append(execute_postgres_statement(statement, request.params))
        total_elapsed_ms = (time.perf_counter() - start) * 1000
        if len(results) == 1:
            return results[0]
        return PostgresQueryBatchResponse(
            results=results,
            statement_count=len(results),
            execution_time_ms=total_elapsed_ms,
        )

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

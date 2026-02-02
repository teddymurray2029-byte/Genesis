from __future__ import annotations

import os
from typing import Any, Iterable, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.sql_utils import normalize_sql
from src.db.genesis_db import GenesisDB

DEFAULT_VOXEL_CLOUD_PATH = os.getenv("GENESIS_VOXEL_CLOUD_PATH")
DEFAULT_DB_PATH = os.getenv("GENESIS_DB_PATH", "data/genesis_db.json")
from src.memory.voxel_cloud import VoxelCloud
from src.api.sql_utils import ensure_readonly_sql

DEFAULT_VOXEL_CLOUD_PATH = os.getenv("GENESIS_VOXEL_CLOUD_PATH")

ENTRY_SCHEMA = [
    {"name": "entry_index", "type": "INTEGER"},
    {"name": "id", "type": "TEXT"},
    {"name": "modality", "type": "TEXT"},
    {"name": "octave", "type": "INTEGER"},
    {"name": "fundamental_freq", "type": "REAL"},
    {"name": "resonance_strength", "type": "INTEGER"},
    {"name": "frequency_band", "type": "INTEGER"},
    {"name": "position_x", "type": "REAL"},
    {"name": "position_y", "type": "REAL"},
    {"name": "position_z", "type": "REAL"},
    {"name": "coherence", "type": "REAL"},
    {"name": "timestamp", "type": "REAL"},
    {"name": "current_state", "type": "TEXT"},
    {"name": "wavecube_x", "type": "INTEGER"},
    {"name": "wavecube_y", "type": "INTEGER"},
    {"name": "wavecube_z", "type": "INTEGER"},
    {"name": "wavecube_w", "type": "REAL"},
    {"name": "cross_modal_links", "type": "TEXT"},
    {"name": "cross_modal_links_json", "type": "TEXT"},
    {"name": "metadata_json", "type": "TEXT"},
    {"name": "proto_identity_json", "type": "TEXT"},
    {"name": "frequency_json", "type": "TEXT"},
    {"name": "position_json", "type": "TEXT"},
    {"name": "mip_levels_json", "type": "TEXT"},
]


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


def create_app(
    voxel_cloud_path: Optional[str] = DEFAULT_VOXEL_CLOUD_PATH,
    db_path: str = DEFAULT_DB_PATH,
) -> FastAPI:
    db = _load_db(db_path, voxel_cloud_path)
    )


def _load_voxel_cloud(path: Optional[str]) -> VoxelCloud:
    voxel_cloud = VoxelCloud()
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"VoxelCloud file not found: {path}")
        voxel_cloud.load(path)
    return voxel_cloud


def _query_entries(voxel_cloud: VoxelCloud, sql: str, params: Iterable[Any]) -> QueryResponse:
    try:
        rows = voxel_cloud.query_by_sql(sql, params)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryResponse(rows=rows, row_count=len(rows))


def create_app(voxel_cloud_path: Optional[str] = DEFAULT_VOXEL_CLOUD_PATH) -> FastAPI:
    voxel_cloud = _load_voxel_cloud(voxel_cloud_path)

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
            "entries": len(voxel_cloud),
            "voxel_cloud_path": voxel_cloud_path,
        }

    @app.get("/schema")
    def schema() -> dict[str, Any]:
        return {"table": "entries", "columns": db.schema}

    @app.post("/query", response_model=QueryResponse)
    def query_entries(request: SqlQuery) -> QueryResponse:
        sql = normalize_sql(request.sql)
        return _query_entries(db, sql, request.params)

    @app.post("/reload")
    def reload_cloud(request: ReloadRequest) -> dict[str, Any]:
        nonlocal db, voxel_cloud_path, db_path
        voxel_cloud_path = request.voxel_cloud_path or voxel_cloud_path
        db_path = request.db_path or db_path
        if not db_path:
            raise HTTPException(status_code=400, detail="GenesisDB path is required")
        db = _load_db(db_path, voxel_cloud_path)
        return {
            "status": "ok",
            "voxel_cloud_path": voxel_cloud_path,
            "db_path": db_path,
            "entries": db.entry_count,
        }
        return {"table": "entries", "columns": ENTRY_SCHEMA}

    @app.post("/query", response_model=QueryResponse)
    def query_entries(request: SqlQuery) -> QueryResponse:
        sql = ensure_readonly_sql(request.sql)
        return _query_entries(voxel_cloud, sql, request.params)

    @app.post("/reload")
    def reload_cloud(request: ReloadRequest) -> dict[str, Any]:
        nonlocal voxel_cloud, voxel_cloud_path
        new_path = request.voxel_cloud_path or voxel_cloud_path
        if not new_path:
            raise HTTPException(status_code=400, detail="VoxelCloud path is required")
        voxel_cloud = _load_voxel_cloud(new_path)
        voxel_cloud_path = new_path
        return {"status": "ok", "voxel_cloud_path": voxel_cloud_path, "entries": len(voxel_cloud)}

    return app


app = create_app()

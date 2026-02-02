from __future__ import annotations

import os
from typing import Any, Iterable, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


class ReloadRequest(BaseModel):
    voxel_cloud_path: Optional[str] = Field(
        default=None,
        description="Optional path to a serialized VoxelCloud pickle.",
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
            "entries": len(voxel_cloud),
            "voxel_cloud_path": voxel_cloud_path,
        }

    @app.get("/schema")
    def schema() -> dict[str, Any]:
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

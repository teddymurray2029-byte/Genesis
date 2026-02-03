"""FastAPI service for the Genesis visualization UI."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from src.db.log_store import LogStore

app = FastAPI(title="Genesis Visualization Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LogEntry(BaseModel):
    id: int
    message: str
    level: str = "info"
    type: str = "event"
    tags: list[str] = Field(default_factory=list)
    created_at: str


class LogCreate(BaseModel):
    message: str
    level: str = "info"
    type: str = "event"
    tags: list[str] = Field(default_factory=list)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json(build_initial_state())
        async with self._lock:
            self._connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._connections)
        if not connections:
            return
        for websocket in connections:
            try:
                await asyncio.wait_for(websocket.send_json(message), timeout=2)
            except Exception:
                await self.disconnect(websocket)

    async def heartbeat(self) -> None:
        await self.broadcast({"type": "heartbeat"})


LOG_STORE = LogStore()
WS_MANAGER = ConnectionManager()


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
    await WS_MANAGER.connect(websocket)
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=15)
                await websocket.send_json({"type": "ack", "message": message})
            except asyncio.TimeoutError:
                await WS_MANAGER.heartbeat()
    except WebSocketDisconnect:
        await WS_MANAGER.disconnect(websocket)
        return


@app.get("/logs")
@app.get("/api/logs")
def list_logs(
    start: str | None = None,
    end: str | None = None,
    log_type: str | None = None,
    tags: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[LogEntry]:
    tag_list = [tag.strip() for tag in tags.split(",")] if tags else []
    try:
        logs = LOG_STORE.list_logs(
            start=start,
            end=end,
            log_type=log_type,
            tags=tag_list,
            offset=offset,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [LogEntry(**entry) for entry in logs]


@app.post("/logs")
@app.post("/api/logs")
def create_log(payload: LogCreate) -> LogEntry:
    entry = LOG_STORE.create_log(
        message=payload.message,
        level=payload.level,
        log_type=payload.type,
        tags=payload.tags,
    )
    asyncio.create_task(WS_MANAGER.broadcast({"type": "log_created", "payload": entry}))
    return LogEntry(**entry)


@app.get("/logs/{log_id}")
@app.get("/api/logs/{log_id}")
def get_log(log_id: int) -> LogEntry:
    entry = LOG_STORE.get_log(log_id)
    if entry is not None:
        return LogEntry(**entry)
    raise HTTPException(status_code=404, detail=f"Log {log_id} not found")


@app.put("/logs/{log_id}")
@app.put("/api/logs/{log_id}")
def update_log(log_id: int, payload: LogCreate) -> LogEntry:
    updated = LOG_STORE.update_log(
        log_id,
        message=payload.message,
        level=payload.level,
        log_type=payload.type,
        tags=payload.tags,
    )
    if updated is not None:
        asyncio.create_task(WS_MANAGER.broadcast({"type": "log_updated", "payload": updated}))
        return LogEntry(**updated)
    raise HTTPException(status_code=404, detail=f"Log {log_id} not found")


@app.delete("/logs/{log_id}")
@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int) -> dict[str, str]:
    if LOG_STORE.delete_log(log_id):
        asyncio.create_task(WS_MANAGER.broadcast({"type": "log_deleted", "payload": {"id": log_id}}))
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail=f"Log {log_id} not found")


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

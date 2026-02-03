"""FastAPI service for the Genesis visualization UI."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

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


class LogCreate(BaseModel):
    message: str
    level: str = "info"


_LOGS: list[LogEntry] = []
_NEXT_LOG_ID = 1


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


_CONNECTIONS = ConnectionManager()


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
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        _CONNECTIONS.disconnect(websocket)
        return


@app.get("/logs")
@app.get("/api/logs")
def list_logs() -> list[LogEntry]:
    return _LOGS


@app.post("/logs")
@app.post("/api/logs")
async def create_log(payload: LogCreate) -> LogEntry:
    global _NEXT_LOG_ID
    entry = LogEntry(id=_NEXT_LOG_ID, message=payload.message, level=payload.level)
    _NEXT_LOG_ID += 1
    _LOGS.append(entry)
    await _CONNECTIONS.broadcast(
        {
            "type": "event",
            "event": {
                "type": "log",
                "message": entry.message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )
    return entry


@app.get("/logs/{log_id}")
@app.get("/api/logs/{log_id}")
def get_log(log_id: int) -> LogEntry:
    for entry in _LOGS:
        if entry.id == log_id:
            return entry
    raise HTTPException(status_code=404, detail=f"Log {log_id} not found")


@app.put("/logs/{log_id}")
@app.put("/api/logs/{log_id}")
def update_log(log_id: int, payload: LogCreate) -> LogEntry:
    for idx, entry in enumerate(_LOGS):
        if entry.id == log_id:
            updated = LogEntry(id=log_id, message=payload.message, level=payload.level)
            _LOGS[idx] = updated
            return updated
    raise HTTPException(status_code=404, detail=f"Log {log_id} not found")


@app.delete("/logs/{log_id}")
@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int) -> dict[str, str]:
    for idx, entry in enumerate(_LOGS):
        if entry.id == log_id:
            del _LOGS[idx]
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

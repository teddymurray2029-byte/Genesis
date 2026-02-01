"""FastAPI service for the Genesis visualization UI."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI(title="Genesis Visualization Service")


@app.get("/health")
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
    await websocket.accept()
    await websocket.send_json(build_initial_state())
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=15)
                await websocket.send_json({"type": "ack", "message": message})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        return


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

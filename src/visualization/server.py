"""FastAPI service for the Genesis visualization UI."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Genesis Visualization Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


LOG_STORE_PATH = Path("data/logs.json")
LOG_LOCK_PATH = Path("data/logs.lock")


class LogEntry(BaseModel):
    id: int
    timestamp: datetime
    type: str
    message: str
    payload: Any | None = None
    tags: list[str] = Field(default_factory=list)


class LogCreate(BaseModel):
    timestamp: datetime | None = None
    type: str
    message: str
    payload: Any | None = None
    tags: list[str] = Field(default_factory=list)


class LogUpdate(BaseModel):
    timestamp: datetime | None = None
    type: str | None = None
    message: str | None = None
    payload: Any | None = None
    tags: list[str] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def interprocess_lock(lock_path: Path) -> Iterable[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, "a", encoding="utf-8")
    lock_file.seek(0)
    try:
        if os.name != "nt":
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        else:
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        yield
    finally:
        if os.name != "nt":
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        else:
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        lock_file.close()


class LogStore:
    def __init__(self, path: Path, lock_path: Path) -> None:
        self._path = path
        self._lock_path = lock_path
        self._lock = Lock()
        self._logs: list[LogEntry] = []
        self._id_index: dict[int, LogEntry] = {}
        self._type_index: dict[str, set[int]] = {}
        self._timestamp_index: list[tuple[datetime, int]] = []
        self._next_id = 1
        self.load()

    def load(self) -> None:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self.save()
            return
        with interprocess_lock(self._lock_path):
            with self._path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        self._logs = [LogEntry(**entry) for entry in raw]
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self._id_index.clear()
        self._type_index.clear()
        self._timestamp_index.clear()
        for entry in self._logs:
            self._id_index[entry.id] = entry
            self._type_index.setdefault(entry.type, set()).add(entry.id)
            self._timestamp_index.append((entry.timestamp, entry.id))
        self._timestamp_index.sort(key=lambda item: item[0])
        self._next_id = max((entry.id for entry in self._logs), default=0) + 1

    def _serialize(self) -> list[dict[str, Any]]:
        return [entry.model_dump(mode="json") for entry in self._logs]

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        with interprocess_lock(self._lock_path):
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(self._serialize(), handle, indent=2, sort_keys=True)
            os.replace(temp_path, self._path)

    def list(self, log_type: str | None = None, start: datetime | None = None, end: datetime | None = None) -> list[LogEntry]:
        with self._lock:
            entries: Iterable[LogEntry] = self._logs
            if log_type:
                ids = self._type_index.get(log_type, set())
                entries = [self._id_index[log_id] for log_id in ids]
            if start or end:
                entries = self._filter_by_timestamp(entries, start, end)
            return list(entries)

    def _filter_by_timestamp(
        self,
        entries: Iterable[LogEntry],
        start: datetime | None,
        end: datetime | None,
    ) -> list[LogEntry]:
        if entries is self._logs:
            index = self._timestamp_index
            left = 0 if start is None else bisect_left(index, (start, 0))
            right = len(index)
            if end is not None:
                right = bisect_left(index, (end, 0))
            return [self._id_index[log_id] for _, log_id in index[left:right]]
        filtered: list[LogEntry] = []
        for entry in entries:
            if start and entry.timestamp < start:
                continue
            if end and entry.timestamp >= end:
                continue
            filtered.append(entry)
        return filtered

    def get(self, log_id: int) -> LogEntry | None:
        return self._id_index.get(log_id)

    def create(self, payload: LogCreate) -> LogEntry:
        with self._lock:
            entry = LogEntry(
                id=self._next_id,
                timestamp=payload.timestamp or _utc_now(),
                type=payload.type,
                message=payload.message,
                payload=payload.payload,
                tags=payload.tags,
            )
            self._next_id += 1
            self._logs.append(entry)
            self._id_index[entry.id] = entry
            self._type_index.setdefault(entry.type, set()).add(entry.id)
            insort(self._timestamp_index, (entry.timestamp, entry.id))
            self.save()
            return entry

    def update(self, log_id: int, payload: LogUpdate) -> LogEntry | None:
        with self._lock:
            entry = self._id_index.get(log_id)
            if entry is None:
                return None
            updated = entry.model_copy(update=payload.model_dump(exclude_unset=True))
            if updated.type != entry.type:
                self._type_index[entry.type].discard(entry.id)
                self._type_index.setdefault(updated.type, set()).add(entry.id)
            if updated.timestamp != entry.timestamp:
                self._timestamp_index.remove((entry.timestamp, entry.id))
                insort(self._timestamp_index, (updated.timestamp, updated.id))
            idx = self._logs.index(entry)
            self._logs[idx] = updated
            self._id_index[updated.id] = updated
            self.save()
            return updated

    def delete(self, log_id: int) -> bool:
        with self._lock:
            entry = self._id_index.get(log_id)
            if entry is None:
                return False
            self._logs.remove(entry)
            del self._id_index[entry.id]
            self._type_index.get(entry.type, set()).discard(entry.id)
            self._timestamp_index.remove((entry.timestamp, entry.id))
            self.save()
            return True


LOG_STORE = LogStore(LOG_STORE_PATH, LOG_LOCK_PATH)


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
def list_logs(
    log_type: str | None = Query(default=None, alias="type"),
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[LogEntry]:
    return LOG_STORE.list(log_type=log_type, start=start, end=end)


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
    entry = LOG_STORE.get(log_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    return entry


@app.put("/logs/{log_id}")
@app.put("/api/logs/{log_id}")
def update_log(log_id: int, payload: LogUpdate) -> LogEntry:
    updated = LOG_STORE.update(log_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")
    return updated


@app.delete("/logs/{log_id}")
@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int) -> dict[str, str]:
    if LOG_STORE.delete(log_id):
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

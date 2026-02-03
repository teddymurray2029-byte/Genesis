from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

DEFAULT_LOG_DB_PATH = os.getenv("GENESIS_LOG_DB_PATH", "data/logs.json")


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LogRecord:
    id: int
    message: str
    level: str = "info"
    type: str = "event"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def matches(
        self,
        start: Optional[datetime],
        end: Optional[datetime],
        log_type: Optional[str],
        tags: Optional[set[str]],
    ) -> bool:
        if log_type and self.type != log_type:
            return False
        if tags and not tags.issubset(set(self.tags)):
            return False
        created = _parse_datetime(self.created_at)
        if created is None:
            return False
        if start and created < start:
            return False
        if end and created > end:
            return False
        return True


class LogStore:
    def __init__(self, db_path: str = DEFAULT_LOG_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logs: list[LogRecord] = []
        self._next_id = 1
        self._load()

    def list_logs(
        self,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        log_type: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        start_dt = _parse_datetime(start)
        end_dt = _parse_datetime(end)
        tag_set = set(tags or [])
        with self._lock:
            filtered = [
                log for log in self._logs
                if log.matches(start_dt, end_dt, log_type, tag_set)
            ]
            sliced = filtered[offset: offset + limit]
            return [asdict(entry) for entry in sliced]

    def get_log(self, log_id: int) -> Optional[dict[str, object]]:
        with self._lock:
            for entry in self._logs:
                if entry.id == log_id:
                    return asdict(entry)
        return None

    def create_log(
        self,
        *,
        message: str,
        level: str = "info",
        log_type: str = "event",
        tags: Optional[Iterable[str]] = None,
    ) -> dict[str, object]:
        with self._lock:
            record = LogRecord(
                id=self._next_id,
                message=message,
                level=level,
                type=log_type,
                tags=list(tags or []),
            )
            self._next_id += 1
            self._logs.append(record)
            self._persist()
            return asdict(record)

    def update_log(
        self,
        log_id: int,
        *,
        message: str,
        level: str = "info",
        log_type: str = "event",
        tags: Optional[Iterable[str]] = None,
    ) -> Optional[dict[str, object]]:
        with self._lock:
            for idx, entry in enumerate(self._logs):
                if entry.id == log_id:
                    updated = LogRecord(
                        id=log_id,
                        message=message,
                        level=level,
                        type=log_type,
                        tags=list(tags or []),
                        created_at=entry.created_at,
                    )
                    self._logs[idx] = updated
                    self._persist()
                    return asdict(updated)
        return None

    def delete_log(self, log_id: int) -> bool:
        with self._lock:
            for idx, entry in enumerate(self._logs):
                if entry.id == log_id:
                    del self._logs[idx]
                    self._persist()
                    return True
        return False

    def _load(self) -> None:
        if not os.path.exists(self._db_path):
            return
        with open(self._db_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("Log store must contain a JSON list")
        self._logs = [LogRecord(**entry) for entry in payload]
        if self._logs:
            self._next_id = max(entry.id for entry in self._logs) + 1

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        tmp_path = f"{self._db_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump([asdict(entry) for entry in self._logs], handle, indent=2)
        os.replace(tmp_path, self._db_path)

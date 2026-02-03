from __future__ import annotations

import json
import os
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Optional


LOG_SCHEMA = [
    {"name": "id", "type": "INTEGER"},
    {"name": "message", "type": "TEXT"},
    {"name": "level", "type": "TEXT"},
]

SCHEMA_COLUMNS = [column["name"] for column in LOG_SCHEMA]


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    columns: list[str]
    affected_rows: int
    operation: str


@dataclass(frozen=True)
class Condition:
    column: str
    operator: str
    value: Any


def resolve_log_db_path(db_path: str) -> str:
    base, ext = os.path.splitext(db_path)
    if ext:
        return f"{base}_logs{ext}"
    return f"{db_path}_logs.json"


class LogStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock_path = f"{db_path}.lock"
        self._lock = threading.RLock()
        self._rows: list[dict[str, Any]] = []
        self._index_by_id: dict[int, dict[str, Any]] = {}
        self._load()

    @property
    def schema(self) -> list[dict[str, str]]:
        return LOG_SCHEMA

    def execute_sql(self, sql: str) -> QueryResult:
        normalized = sql.strip().rstrip(";").strip()
        if not normalized:
            raise ValueError("SQL query must not be empty")
        command = normalized.split()[0].lower()
        if command == "select":
            return self._select(normalized)
        if command == "insert":
            return self._insert(normalized)
        if command == "update":
            return self._update(normalized)
        if command == "delete":
            return self._delete(normalized)
        raise ValueError("Only SELECT, INSERT, UPDATE, and DELETE statements are supported")

    def _load(self) -> None:
        with self._interprocess_lock():
            if os.path.exists(self._db_path):
                with open(self._db_path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                if not isinstance(payload, list):
                    raise ValueError("Log store file must contain a JSON list of rows")
                self._rows = payload
        self._rebuild_indexes()

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        tmp_path = f"{self._db_path}.tmp"
        with self._interprocess_lock():
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(self._rows, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self._db_path)

    @contextmanager
    def _interprocess_lock(self, retries: int = 10, delay: float = 0.1) -> Iterable[None]:
        os.makedirs(os.path.dirname(self._lock_path) or ".", exist_ok=True)
        lock_file = open(self._lock_path, "a", encoding="utf-8")
        lock_file.seek(0)
        attempts = 0
        while True:
            try:
                if os.name != "nt":
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    import msvcrt

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                attempts += 1
                if attempts > retries:
                    lock_file.close()
                    raise TimeoutError("Timed out waiting for log store lock") from exc
                time.sleep(delay)
        try:
            yield
        finally:
            if os.name != "nt":
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            else:
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            lock_file.close()

    def _rebuild_indexes(self) -> None:
        self._index_by_id = {}
        for row in self._rows:
            entry_id = row.get("id")
            if isinstance(entry_id, int):
                self._index_by_id[entry_id] = row

    def _select(self, sql: str) -> QueryResult:
        match = re.match(
            r"^select\s+(?P<select>.+?)\s+from\s+logs"
            r"(?:\s+where\s+(?P<where>.+?))?"
            r"(?:\s+order\s+by\s+(?P<order>.+?))?"
            r"(?:\s+limit\s+(?P<limit>\d+))?$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid SELECT syntax; expected SELECT ... FROM logs")

        select_clause = match.group("select").strip()
        where_clause = match.group("where")
        order_clause = match.group("order")
        limit_clause = match.group("limit")

        columns, aliases = self._parse_select_columns(select_clause)
        conditions = self._parse_conditions(where_clause)

        with self._lock:
            rows = list(self._iter_filtered_rows(conditions))

        if order_clause:
            rows = self._apply_order_by(rows, order_clause)

        if limit_clause:
            rows = rows[: int(limit_clause)]

        projected = [{alias: row.get(column) for alias, column in aliases.items()} for row in rows]
        return QueryResult(rows=projected, columns=list(aliases.keys()), affected_rows=0, operation="select")

    def _insert(self, sql: str) -> QueryResult:
        match = re.match(
            r"^insert\s+into\s+logs(?:\s*\((?P<cols>.+?)\))?\s+values\s*\((?P<vals>.+)\)$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid INSERT syntax; expected INSERT INTO logs (...) VALUES (...)")

        columns = self._parse_csv(match.group("cols")) if match.group("cols") else SCHEMA_COLUMNS
        values = self._parse_csv(match.group("vals"))
        if len(columns) != len(values):
            raise ValueError("INSERT columns and values must have the same length")

        row = {column: None for column in SCHEMA_COLUMNS}
        for column, value in zip(columns, values):
            column_name = self._normalize_column(column)
            row[column_name] = self._parse_literal(value)

        with self._lock:
            if row.get("id") is None:
                next_id = max(self._index_by_id.keys(), default=0) + 1
                row["id"] = next_id
            self._ensure_unique_keys(row)
            self._rows.append(row)
            self._index_by_id[row["id"]] = row
            self._persist()

        return QueryResult(rows=[], columns=[], affected_rows=1, operation="insert")

    def _update(self, sql: str) -> QueryResult:
        match = re.match(
            r"^update\s+logs\s+set\s+(?P<assign>.+?)(?:\s+where\s+(?P<where>.+))?$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid UPDATE syntax; expected UPDATE logs SET ... WHERE ...")

        assignments = self._parse_assignments(match.group("assign"))
        conditions = self._parse_conditions(match.group("where"))

        updated = 0
        with self._lock:
            rows = list(self._iter_filtered_rows(conditions))
            for row in rows:
                updated += 1
                original_id = row.get("id")
                for column, value in assignments.items():
                    row[column] = value
                self._ensure_unique_keys(row, original_id)
                if original_id != row.get("id"):
                    self._index_by_id.pop(original_id, None)
                    self._index_by_id[row["id"]] = row
            if updated:
                self._persist()

        return QueryResult(rows=[], columns=[], affected_rows=updated, operation="update")

    def _delete(self, sql: str) -> QueryResult:
        match = re.match(
            r"^delete\s+from\s+logs(?:\s+where\s+(?P<where>.+))?$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid DELETE syntax; expected DELETE FROM logs WHERE ...")

        conditions = self._parse_conditions(match.group("where"))
        deleted = 0
        with self._lock:
            remaining = []
            for row in self._rows:
                if self._row_matches(row, conditions):
                    deleted += 1
                    continue
                remaining.append(row)
            if deleted:
                self._rows = remaining
                self._rebuild_indexes()
                self._persist()

        return QueryResult(rows=[], columns=[], affected_rows=deleted, operation="delete")

    def _parse_select_columns(self, clause: str) -> tuple[list[str], dict[str, str]]:
        clause = clause.strip()
        if clause == "*":
            aliases = {column: column for column in SCHEMA_COLUMNS}
            return SCHEMA_COLUMNS, aliases

        columns = []
        aliases: dict[str, str] = {}
        for raw in self._parse_csv(clause):
            raw = raw.strip()
            if not raw:
                continue
            parts = re.split(r"\s+as\s+", raw, flags=re.IGNORECASE)
            column = self._normalize_column(parts[0])
            alias = parts[1].strip() if len(parts) > 1 else column
            columns.append(column)
            aliases[alias] = column
        return columns, aliases

    def _parse_conditions(self, clause: Optional[str]) -> list[Condition]:
        if not clause:
            return []
        parts = re.split(r"\s+and\s+", clause, flags=re.IGNORECASE)
        conditions: list[Condition] = []
        for part in parts:
            match = re.match(r"^\s*(\S+)\s*(=|!=|<>|<=|>=|<|>)\s*(.+)\s*$", part)
            if not match:
                raise ValueError(f"Unsupported WHERE condition: {part}")
            column = self._normalize_column(match.group(1))
            operator = match.group(2)
            value = self._parse_literal(match.group(3))
            conditions.append(Condition(column=column, operator=operator, value=value))
        return conditions

    def _parse_assignments(self, clause: str) -> dict[str, Any]:
        assignments: dict[str, Any] = {}
        for assignment in self._parse_csv(clause):
            match = re.match(r"^\s*(\S+)\s*=\s*(.+)\s*$", assignment)
            if not match:
                raise ValueError(f"Invalid assignment: {assignment}")
            column = self._normalize_column(match.group(1))
            assignments[column] = self._parse_literal(match.group(2))
        return assignments

    def _normalize_column(self, raw: str) -> str:
        column = raw.strip()
        if "." in column:
            column = column.split(".")[-1]
        if column not in SCHEMA_COLUMNS:
            raise ValueError(f"Unknown column '{column}'")
        return column

    def _parse_csv(self, clause: str) -> list[str]:
        items: list[str] = []
        current = []
        in_single = False
        in_double = False
        for char in clause:
            if char == "'" and not in_double:
                in_single = not in_single
                current.append(char)
                continue
            if char == '"' and not in_single:
                in_double = not in_double
                current.append(char)
                continue
            if char == "," and not in_single and not in_double:
                items.append("".join(current).strip())
                current = []
                continue
            current.append(char)
        if current:
            items.append("".join(current).strip())
        return items

    def _parse_literal(self, raw: str) -> Any:
        value = raw.strip()
        if value.lower() == "null":
            return None
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            return value[1:-1].replace("\\'", "'").replace('\\"', '"')
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value

    def _row_matches(self, row: dict[str, Any], conditions: Iterable[Condition]) -> bool:
        for condition in conditions:
            left = row.get(condition.column)
            right = condition.value
            if condition.operator in ("=", "==") and left != right:
                return False
            if condition.operator in ("!=", "<>") and left == right:
                return False
            if condition.operator == "<" and not (left is not None and right is not None and left < right):
                return False
            if condition.operator == ">" and not (left is not None and right is not None and left > right):
                return False
            if condition.operator == "<=" and not (left is not None and right is not None and left <= right):
                return False
            if condition.operator == ">=" and not (left is not None and right is not None and left >= right):
                return False
        return True

    def _iter_filtered_rows(self, conditions: list[Condition]) -> Iterable[dict[str, Any]]:
        if len(conditions) == 1 and conditions[0].operator == "=":
            condition = conditions[0]
            if condition.column == "id" and isinstance(condition.value, int):
                row = self._index_by_id.get(condition.value)
                if row is not None:
                    yield row
                return
        for row in self._rows:
            if self._row_matches(row, conditions):
                yield row

    def _apply_order_by(self, rows: list[dict[str, Any]], clause: str) -> list[dict[str, Any]]:
        parts = self._parse_csv(clause)
        if not parts:
            return rows
        first = parts[0].strip()
        tokens = first.split()
        column = self._normalize_column(tokens[0])
        descending = len(tokens) > 1 and tokens[1].lower() == "desc"
        return sorted(rows, key=lambda row: row.get(column), reverse=descending)

    def _ensure_unique_keys(self, row: dict[str, Any], original_id: Optional[int] = None) -> None:
        entry_id = row.get("id")
        if entry_id is not None and entry_id != original_id:
            if entry_id in self._index_by_id:
                raise ValueError(f"id {entry_id} already exists")

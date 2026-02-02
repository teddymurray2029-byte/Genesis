from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from src.memory.voxel_cloud import VoxelCloud
from src.memory.voxel_cloud_query import _encode_array, _encode_mip_levels


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

SCHEMA_COLUMNS = [column["name"] for column in ENTRY_SCHEMA]


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


class GenesisDB:
    def __init__(self, db_path: str, voxel_cloud_path: Optional[str] = None) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._rows: list[dict[str, Any]] = []
        self._index_by_entry_index: dict[int, dict[str, Any]] = {}
        self._index_by_id: dict[str, dict[str, Any]] = {}
        self._load(voxel_cloud_path)

    @property
    def schema(self) -> list[dict[str, str]]:
        return ENTRY_SCHEMA

    @property
    def entry_count(self) -> int:
        return len(self._rows)

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

    def _load(self, voxel_cloud_path: Optional[str]) -> None:
        if os.path.exists(self._db_path):
            with open(self._db_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, list):
                raise ValueError("GenesisDB file must contain a JSON list of rows")
            self._rows = payload
            self._rebuild_indexes()
            return

        if voxel_cloud_path:
            voxel_cloud = VoxelCloud()
            if not os.path.exists(voxel_cloud_path):
                raise FileNotFoundError(f"VoxelCloud file not found: {voxel_cloud_path}")
            voxel_cloud.load(voxel_cloud_path)
            self._rows = [self._row_from_entry(index, entry) for index, entry in enumerate(voxel_cloud.entries)]
            self._rebuild_indexes()
            self._persist()

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        tmp_path = f"{self._db_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self._rows, handle, indent=2)
        os.replace(tmp_path, self._db_path)

    def _rebuild_indexes(self) -> None:
        self._index_by_entry_index = {}
        self._index_by_id = {}
        for row in self._rows:
            entry_index = row.get("entry_index")
            if isinstance(entry_index, int):
                self._index_by_entry_index[entry_index] = row
            entry_id = row.get("id")
            if isinstance(entry_id, str):
                self._index_by_id[entry_id] = row

    def _row_from_entry(self, entry_index: int, entry: Any) -> dict[str, Any]:
        metadata = entry.metadata or {}
        wavecube_coords = entry.wavecube_coords or (None, None, None, None)
        cross_modal_links = ",".join(entry.cross_modal_links)
        cross_modal_links_json = json.dumps(entry.cross_modal_links, default=str)
        metadata_json = json.dumps(metadata, default=str)
        proto_identity_json = _encode_array(entry.proto_identity)
        frequency_json = _encode_array(entry.frequency)
        position_json = _encode_array(entry.position)
        mip_levels_json = _encode_mip_levels(entry.mip_levels)

        return {
            "entry_index": entry_index,
            "id": metadata.get("id", str(id(entry))),
            "modality": entry.modality,
            "octave": entry.octave,
            "fundamental_freq": entry.fundamental_freq,
            "resonance_strength": entry.resonance_strength,
            "frequency_band": entry.frequency_band,
            "position_x": float(entry.position[0]),
            "position_y": float(entry.position[1]),
            "position_z": float(entry.position[2]),
            "coherence": entry.coherence_vs_core,
            "timestamp": metadata.get("timestamp"),
            "current_state": entry.current_state.name if entry.current_state else None,
            "wavecube_x": wavecube_coords[0],
            "wavecube_y": wavecube_coords[1],
            "wavecube_z": wavecube_coords[2],
            "wavecube_w": wavecube_coords[3],
            "cross_modal_links": cross_modal_links,
            "cross_modal_links_json": cross_modal_links_json,
            "metadata_json": metadata_json,
            "proto_identity_json": proto_identity_json,
            "frequency_json": frequency_json,
            "position_json": position_json,
            "mip_levels_json": mip_levels_json,
        }

    def _select(self, sql: str) -> QueryResult:
        match = re.match(
            r"^select\s+(?P<select>.+?)\s+from\s+entries"
            r"(?:\s+where\s+(?P<where>.+?))?"
            r"(?:\s+order\s+by\s+(?P<order>.+?))?"
            r"(?:\s+limit\s+(?P<limit>\d+))?$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid SELECT syntax; expected SELECT ... FROM entries")

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

        projected = [
            {alias: row.get(column) for alias, column in aliases.items()}
            for row in rows
        ]
        return QueryResult(rows=projected, columns=list(aliases.keys()), affected_rows=0, operation="select")

    def _insert(self, sql: str) -> QueryResult:
        match = re.match(
            r"^insert\s+into\s+entries(?:\s*\((?P<cols>.+?)\))?\s+values\s*\((?P<vals>.+)\)$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid INSERT syntax; expected INSERT INTO entries (...) VALUES (...)")

        columns = self._parse_csv(match.group("cols")) if match.group("cols") else SCHEMA_COLUMNS
        values = self._parse_csv(match.group("vals"))
        if len(columns) != len(values):
            raise ValueError("INSERT columns and values must have the same length")

        row = {column: None for column in SCHEMA_COLUMNS}
        for column, value in zip(columns, values):
            column_name = self._normalize_column(column)
            row[column_name] = self._parse_literal(value)

        with self._lock:
            if row.get("entry_index") is None:
                next_index = max(self._index_by_entry_index.keys(), default=-1) + 1
                row["entry_index"] = next_index
            if row.get("id") is None:
                row["id"] = str(uuid.uuid4())
            self._ensure_unique_keys(row)
            self._rows.append(row)
            self._index_by_entry_index[row["entry_index"]] = row
            self._index_by_id[row["id"]] = row
            self._persist()

        return QueryResult(rows=[], columns=[], affected_rows=1, operation="insert")

    def _update(self, sql: str) -> QueryResult:
        match = re.match(
            r"^update\s+entries\s+set\s+(?P<assign>.+?)(?:\s+where\s+(?P<where>.+))?$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid UPDATE syntax; expected UPDATE entries SET ... WHERE ...")

        assignments = self._parse_assignments(match.group("assign"))
        conditions = self._parse_conditions(match.group("where"))

        updated = 0
        with self._lock:
            rows = list(self._iter_filtered_rows(conditions))
            for row in rows:
                updated += 1
                original_id = row.get("id")
                original_entry_index = row.get("entry_index")
                for column, value in assignments.items():
                    row[column] = value
                self._ensure_unique_keys(row, original_id, original_entry_index)
                if original_entry_index != row.get("entry_index"):
                    self._index_by_entry_index.pop(original_entry_index, None)
                    self._index_by_entry_index[row["entry_index"]] = row
                if original_id != row.get("id"):
                    self._index_by_id.pop(original_id, None)
                    self._index_by_id[row["id"]] = row
            if updated:
                self._persist()

        return QueryResult(rows=[], columns=[], affected_rows=updated, operation="update")

    def _delete(self, sql: str) -> QueryResult:
        match = re.match(
            r"^delete\s+from\s+entries(?:\s+where\s+(?P<where>.+))?$",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Invalid DELETE syntax; expected DELETE FROM entries WHERE ...")

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
        if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
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
            if condition.column == "entry_index" and isinstance(condition.value, int):
                row = self._index_by_entry_index.get(condition.value)
                if row is not None:
                    yield row
                return
            if condition.column == "id" and isinstance(condition.value, str):
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

    def _ensure_unique_keys(
        self,
        row: dict[str, Any],
        original_id: Optional[str] = None,
        original_entry_index: Optional[int] = None,
    ) -> None:
        entry_index = row.get("entry_index")
        if entry_index is not None and entry_index != original_entry_index:
            if entry_index in self._index_by_entry_index:
                raise ValueError(f"entry_index {entry_index} already exists")
        entry_id = row.get("id")
        if entry_id is not None and entry_id != original_id:
            if entry_id in self._index_by_id:
                raise ValueError(f"id {entry_id} already exists")

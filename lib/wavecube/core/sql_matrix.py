"""
SQLite-backed wavetable matrix for SQL CRUD access.

Provides SQLWavetableMatrix with a standard SQL schema so external
code can read/write/query wavetables using existing SQL tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from typing import Any, Dict, Iterable, Optional, Tuple, Union

import numpy as np


@dataclass(frozen=True)
class SQLWavetableSchema:
    """Schema metadata for SQLWavetableMatrix storage."""

    table_name: str = "wavetable_nodes"

    def create_table_sql(self) -> str:
        return f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            z INTEGER NOT NULL,
            wavetable BLOB NOT NULL,
            resolution_h INTEGER NOT NULL,
            resolution_w INTEGER NOT NULL,
            channels INTEGER NOT NULL,
            dtype TEXT NOT NULL,
            metadata TEXT NOT NULL,
            PRIMARY KEY (x, y, z)
        )
        """.strip()


class SQLWavetableMatrix:
    """
    3D wavetable matrix stored in SQLite for SQL CRUD access.

    Uses a simple SQL schema so external clients can query/insert/update/delete
    nodes with standard SQL. Wavetable arrays are stored as raw bytes with
    explicit shape and dtype metadata.
    """

    def __init__(
        self,
        width: int,
        height: int,
        depth: int,
        resolution: Union[Tuple[int, int], int] = 512,
        channels: int = 4,
        dtype: np.dtype = np.float32,
        db_path: str = ":memory:",
        schema: Optional[SQLWavetableSchema] = None,
    ) -> None:
        if width <= 0 or height <= 0 or depth <= 0:
            raise ValueError(f"Grid dimensions must be positive: {width}×{height}×{depth}")

        self.width = width
        self.height = height
        self.depth = depth
        self.channels = channels
        self.dtype = np.dtype(dtype)
        self.resolution = (resolution, resolution) if isinstance(resolution, int) else resolution
        self.schema = schema or SQLWavetableSchema()

        self._connection = sqlite3.connect(db_path)
        self._connection.execute(self.schema.create_table_sql())
        self._connection.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        """Expose the underlying SQLite connection for direct SQL access."""

        return self._connection

    def close(self) -> None:
        """Close the SQLite connection."""

        self._connection.close()

    def _validate_coordinates(self, x: int, y: int, z: int) -> None:
        if not (0 <= x < self.width):
            raise IndexError(f"X coordinate {x} out of bounds [0, {self.width})")
        if not (0 <= y < self.height):
            raise IndexError(f"Y coordinate {y} out of bounds [0, {self.height})")
        if not (0 <= z < self.depth):
            raise IndexError(f"Z coordinate {z} out of bounds [0, {self.depth})")

    @staticmethod
    def serialize_wavetable(wavetable: np.ndarray) -> Tuple[bytes, Tuple[int, int, int], str]:
        """
        Serialize a wavetable to raw bytes with shape and dtype metadata.
        """

        if wavetable.ndim != 3:
            raise ValueError(f"Wavetable must be 3D (H, W, C), got {wavetable.ndim}D")

        dtype = np.dtype(wavetable.dtype)
        return wavetable.tobytes(order="C"), wavetable.shape, dtype.str

    @staticmethod
    def deserialize_wavetable(
        blob: bytes,
        shape: Tuple[int, int, int],
        dtype: str,
    ) -> np.ndarray:
        """Deserialize wavetable from raw bytes with shape and dtype."""

        array = np.frombuffer(blob, dtype=np.dtype(dtype)).reshape(shape)
        return array.copy()

    def set_node(
        self,
        x: int,
        y: int,
        z: int,
        wavetable: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Insert or update a wavetable at grid position (x, y, z).
        """

        self._validate_coordinates(x, y, z)

        blob, shape, dtype = self.serialize_wavetable(wavetable.astype(self.dtype))
        metadata_json = json.dumps(metadata or {})

        self._connection.execute(
            f"""
            INSERT INTO {self.schema.table_name}
                (x, y, z, wavetable, resolution_h, resolution_w, channels, dtype, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(x, y, z) DO UPDATE SET
                wavetable=excluded.wavetable,
                resolution_h=excluded.resolution_h,
                resolution_w=excluded.resolution_w,
                channels=excluded.channels,
                dtype=excluded.dtype,
                metadata=excluded.metadata
            """.strip(),
            (x, y, z, blob, shape[0], shape[1], shape[2], dtype, metadata_json),
        )
        self._connection.commit()

    def get_node(self, x: int, y: int, z: int) -> Optional[np.ndarray]:
        """Fetch wavetable at grid position (x, y, z) or None."""

        self._validate_coordinates(x, y, z)
        cursor = self._connection.execute(
            f"""
            SELECT wavetable, resolution_h, resolution_w, channels, dtype
            FROM {self.schema.table_name}
            WHERE x = ? AND y = ? AND z = ?
            """.strip(),
            (x, y, z),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        blob, h, w, c, dtype = row
        return self.deserialize_wavetable(blob, (h, w, c), dtype)

    def get_metadata(self, x: int, y: int, z: int) -> Optional[Dict[str, Any]]:
        """Fetch metadata for node at grid position (x, y, z)."""

        self._validate_coordinates(x, y, z)
        cursor = self._connection.execute(
            f"""
            SELECT metadata
            FROM {self.schema.table_name}
            WHERE x = ? AND y = ? AND z = ?
            """.strip(),
            (x, y, z),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def has_node(self, x: int, y: int, z: int) -> bool:
        """Check if node exists at position."""

        self._validate_coordinates(x, y, z)
        cursor = self._connection.execute(
            f"""
            SELECT 1
            FROM {self.schema.table_name}
            WHERE x = ? AND y = ? AND z = ?
            """.strip(),
            (x, y, z),
        )
        return cursor.fetchone() is not None

    def delete_node(self, x: int, y: int, z: int) -> None:
        """Delete node at position."""

        self._validate_coordinates(x, y, z)
        self._connection.execute(
            f"""
            DELETE FROM {self.schema.table_name}
            WHERE x = ? AND y = ? AND z = ?
            """.strip(),
            (x, y, z),
        )
        self._connection.commit()

    def execute(
        self,
        sql: str,
        parameters: Optional[Iterable[Any]] = None,
    ) -> sqlite3.Cursor:
        """
        Execute raw SQL against the backing store.

        This enables external code to run arbitrary SQL CRUD commands.
        """

        cursor = self._connection.execute(sql, tuple(parameters or ()))
        self._connection.commit()
        return cursor

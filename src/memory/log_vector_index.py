from __future__ import annotations

import threading
from typing import Iterable

import numpy as np


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


class LogVectorIndex:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self._vectors: dict[int, np.ndarray] = {}
        self._lock = threading.Lock()

    def upsert(self, entry_id: int, vector: np.ndarray) -> None:
        if vector.shape[0] != self.dim:
            raise ValueError("Vector dimension does not match index")
        with self._lock:
            self._vectors[entry_id] = _normalize_vector(vector)

    def remove(self, entry_id: int) -> None:
        with self._lock:
            self._vectors.pop(entry_id, None)

    def search(self, query_vector: np.ndarray, limit: int = 5) -> list[tuple[int, float]]:
        if limit <= 0:
            return []
        query_vector = _normalize_vector(query_vector)
        with self._lock:
            items = list(self._vectors.items())
        if not items:
            return []
        scores = [(entry_id, float(np.dot(query_vector, vector))) for entry_id, vector in items]
        scores.sort(key=lambda pair: pair[1], reverse=True)
        return scores[:limit]

    def bulk_upsert(self, items: Iterable[tuple[int, np.ndarray]]) -> None:
        with self._lock:
            for entry_id, vector in items:
                if vector.shape[0] != self.dim:
                    raise ValueError("Vector dimension does not match index")
                self._vectors[entry_id] = _normalize_vector(vector)

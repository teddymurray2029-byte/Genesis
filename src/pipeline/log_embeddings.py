from __future__ import annotations

import hashlib
import json
import queue
import re
import threading
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _stable_hash(token: str) -> bytes:
    return hashlib.sha1(token.encode("utf-8")).digest()


@dataclass(frozen=True)
class EmbeddedLog:
    entry_id: int
    vector: np.ndarray


class LogEmbeddingPipeline:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed_entry(self, entry: Mapping[str, Any]) -> np.ndarray:
        text = self._build_text(entry)
        return self._embed_text(text)

    def embed_text(self, text: str) -> np.ndarray:
        return self._embed_text(text)

    def _embed_text(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dim, dtype=np.float32)
        for token in _TOKEN_PATTERN.findall(text.lower()):
            digest = _stable_hash(token)
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1 if digest[4] % 2 == 0 else -1
            vector[bucket] += sign
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector

    def _build_text(self, entry: Mapping[str, Any]) -> str:
        parts = []
        message = entry.get("message")
        if message:
            parts.append(str(message))
        entry_type = entry.get("type")
        if entry_type:
            parts.append(str(entry_type))
        tags = entry.get("tags")
        if tags:
            parts.append(" ".join(str(tag) for tag in tags))
        payload = entry.get("payload")
        if payload:
            if isinstance(payload, (dict, list)):
                parts.append(json.dumps(payload, ensure_ascii=False))
            else:
                parts.append(str(payload))
        return " ".join(parts)


class LogEmbeddingWorker:
    def __init__(self, pipeline: LogEmbeddingPipeline, vector_index: Any) -> None:
        self._pipeline = pipeline
        self._vector_index = vector_index
        self._queue: queue.Queue[Mapping[str, Any]] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def enqueue(self, entry: Mapping[str, Any]) -> None:
        self._queue.put(entry)

    def _run(self) -> None:
        while True:
            entry = self._queue.get()
            try:
                entry_id = entry.get("id")
                if entry_id is None:
                    continue
                vector = self._pipeline.embed_entry(entry)
                self._vector_index.upsert(int(entry_id), vector)
            finally:
                self._queue.task_done()

"""Minimal psutil shim for test environments without psutil installed."""

from __future__ import annotations

import os
import resource
from collections import namedtuple


MemoryInfo = namedtuple("pmem", ["rss"])


class Process:
    def __init__(self, pid: int | None = None) -> None:
        self._pid = pid or os.getpid()

    def memory_info(self) -> MemoryInfo:
        # ru_maxrss is in kilobytes on Linux.
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_bytes = int(usage.ru_maxrss) * 1024
        return MemoryInfo(rss=rss_bytes)

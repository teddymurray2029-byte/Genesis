from __future__ import annotations

import re

from fastapi import HTTPException

_SQL_READONLY_PATTERN = re.compile(r"^\s*(with|select)\b", re.IGNORECASE | re.DOTALL)


def ensure_readonly_sql(sql: str) -> str:
    stripped = sql.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="SQL query must not be empty")
    normalized = stripped.rstrip(";")
    if ";" in normalized:
        raise HTTPException(status_code=400, detail="Multiple SQL statements are not allowed")
    if not _SQL_READONLY_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")
    return normalized

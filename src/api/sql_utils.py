from __future__ import annotations

import re

from fastapi import HTTPException

_SQL_READONLY_PATTERN = re.compile(r"^\s*(with|select)\b", re.IGNORECASE | re.DOTALL)
_DOLLAR_QUOTE_PATTERN = re.compile(r"^\$[A-Za-z0-9_]*\$$")


def normalize_sql(sql: str) -> str:
    stripped = sql.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="SQL query must not be empty")
    normalized = stripped.rstrip(";")
    if ";" in normalized:
        raise HTTPException(status_code=400, detail="Multiple SQL statements are not allowed")
    return normalized


def normalize_sql_statement(statement: str) -> str:
    stripped = statement.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="SQL query must not be empty")
    return stripped.rstrip(";").strip()


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: str | None = None
    i = 0
    length = len(sql)

    while i < length:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < length else ""

        if in_line_comment:
            buffer.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buffer.append(ch)
            if ch == "*" and nxt == "/":
                buffer.append(nxt)
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buffer.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buffer.append(ch)
            i += 1
            continue

        if not in_single and not in_double:
            if ch == "-" and nxt == "-":
                buffer.append(ch)
                buffer.append(nxt)
                i += 2
                in_line_comment = True
                continue
            if ch == "/" and nxt == "*":
                buffer.append(ch)
                buffer.append(nxt)
                i += 2
                in_block_comment = True
                continue

        if ch == "'" and not in_double:
            buffer.append(ch)
            if in_single and nxt == "'":
                buffer.append(nxt)
                i += 2
                continue
            in_single = not in_single
            i += 1
            continue

        if ch == '"' and not in_single:
            buffer.append(ch)
            if in_double and nxt == '"':
                buffer.append(nxt)
                i += 2
                continue
            in_double = not in_double
            i += 1
            continue

        if ch == "$" and not in_single and not in_double:
            end = sql.find("$", i + 1)
            if end != -1:
                candidate = sql[i : end + 1]
                if _DOLLAR_QUOTE_PATTERN.match(candidate):
                    buffer.append(candidate)
                    dollar_tag = candidate
                    i = end + 1
                    continue

        if ch == ";" and not in_single and not in_double:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            i += 1
            continue

        buffer.append(ch)
        i += 1

    remainder = "".join(buffer).strip()
    if remainder:
        statements.append(remainder)

    return statements


def parse_sql_statements(sql: str) -> list[str]:
    if not sql or not sql.strip():
        raise HTTPException(status_code=400, detail="SQL query must not be empty")
    statements = [normalize_sql_statement(stmt) for stmt in split_sql_statements(sql)]
    if not statements:
        raise HTTPException(status_code=400, detail="SQL query must not be empty")
    return statements


def ensure_readonly_sql(sql: str) -> str:
    normalized = normalize_sql(sql)
    if not _SQL_READONLY_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")
    return normalized

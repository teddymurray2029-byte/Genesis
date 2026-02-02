from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import struct
from dataclasses import dataclass
from typing import Iterable, Optional

from src.api.sql_utils import normalize_sql
from src.db.genesis_db import GenesisDB

LOGGER = logging.getLogger(__name__)

DEFAULT_VOXEL_CLOUD_PATH = os.getenv("GENESIS_VOXEL_CLOUD_PATH")
DEFAULT_DB_PATH = os.getenv("GENESIS_DB_PATH", "data/genesis_db.json")
DEFAULT_HOST = os.getenv("GENESIS_MYSQL_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("GENESIS_MYSQL_PORT", "3306"))
DEFAULT_USER = os.getenv("GENESIS_MYSQL_USER", "genesis")
DEFAULT_PASSWORD = os.getenv("GENESIS_MYSQL_PASSWORD", "")

SERVER_VERSION = os.getenv("GENESIS_MYSQL_SERVER_VERSION", "5.7.0-genesis")

CLIENT_LONG_PASSWORD = 0x00000001
CLIENT_LONG_FLAG = 0x00000004
CLIENT_CONNECT_WITH_DB = 0x00000008
CLIENT_PROTOCOL_41 = 0x00000200
CLIENT_SECURE_CONNECTION = 0x00008000
CLIENT_PLUGIN_AUTH = 0x00080000
CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA = 0x00200000

MYSQL_TYPE_LONGLONG = 0x08
MYSQL_TYPE_DOUBLE = 0x05
MYSQL_TYPE_VAR_STRING = 0xfd


@dataclass
class ClientContext:
    user: str
    capabilities: int


def _pack_packet(payload: bytes, sequence_id: int) -> bytes:
    header = struct.pack("<I", len(payload))[:3] + struct.pack("B", sequence_id)
    return header + payload


def _read_null_terminated(payload: bytes, offset: int) -> tuple[str, int]:
    end = payload.index(b"\x00", offset)
    return payload[offset:end].decode("utf-8", errors="replace"), end + 1


def _read_null_bytes(payload: bytes, offset: int) -> tuple[bytes, int]:
    end = payload.index(b"\x00", offset)
    return payload[offset:end], end + 1


def _read_lenenc_int(payload: bytes, offset: int) -> tuple[int, int]:
    first = payload[offset]
    offset += 1
    if first < 0xfb:
        return first, offset
    if first == 0xfc:
        value = int.from_bytes(payload[offset:offset + 2], "little")
        return value, offset + 2
    if first == 0xfd:
        value = int.from_bytes(payload[offset:offset + 3], "little")
        return value, offset + 3
    if first == 0xfe:
        value = int.from_bytes(payload[offset:offset + 8], "little")
        return value, offset + 8
    raise ValueError("Invalid length-encoded integer marker")


def _pack_lenenc_int(value: int) -> bytes:
    if value < 0xfb:
        return struct.pack("B", value)
    if value < 2**16:
        return b"\xfc" + struct.pack("<H", value)
    if value < 2**24:
        return b"\xfd" + struct.pack("<I", value)[:3]
    return b"\xfe" + struct.pack("<Q", value)


def _pack_lenenc_str(value: str | bytes) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return _pack_lenenc_int(len(value)) + value


def _scramble_password(password: str, salt: bytes) -> bytes:
    if not password:
        return b""
    stage1 = hashlib.sha1(password.encode("utf-8")).digest()
    stage2 = hashlib.sha1(stage1).digest()
    stage3 = hashlib.sha1(salt + stage2).digest()
    return bytes(x ^ y for x, y in zip(stage3, stage1))


def _ok_packet(affected_rows: int = 0) -> bytes:
    return b"\x00" + _pack_lenenc_int(affected_rows) + _pack_lenenc_int(0) + struct.pack("<HH", 2, 0)


def _error_packet(message: str, code: int = 1064, sql_state: str = "42000") -> bytes:
    return b"\xff" + struct.pack("<H", code) + b"#" + sql_state.encode("ascii") + message.encode("utf-8")


def _eof_packet() -> bytes:
    return b"\xfe" + struct.pack("<HH", 0, 2)


def _column_type_from_value(value: object) -> int:
    if isinstance(value, bool):
        return MYSQL_TYPE_LONGLONG
    if isinstance(value, int):
        return MYSQL_TYPE_LONGLONG
    if isinstance(value, float):
        return MYSQL_TYPE_DOUBLE
    return MYSQL_TYPE_VAR_STRING


def _column_definition(name: str, column_type: int) -> bytes:
    catalog = _pack_lenenc_str("def")
    schema = _pack_lenenc_str("")
    table = _pack_lenenc_str("entries")
    org_table = _pack_lenenc_str("")
    column_name = _pack_lenenc_str(name)
    org_name = _pack_lenenc_str(name)
    fixed_length = struct.pack("B", 0x0c)
    charset = struct.pack("<H", 0x21)
    column_length = struct.pack("<I", 1024)
    type_and_flags = struct.pack("B", column_type) + struct.pack("<H", 0) + struct.pack("B", 0)
    filler = struct.pack("<H", 0)
    return b"".join(
        [
            catalog,
            schema,
            table,
            org_table,
            column_name,
            org_name,
            fixed_length,
            charset,
            column_length,
            type_and_flags,
            filler,
        ]
    )


class MySQLGateway:
    def __init__(
        self,
        voxel_cloud_path: Optional[str] = DEFAULT_VOXEL_CLOUD_PATH,
        db_path: str = DEFAULT_DB_PATH,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
    ) -> None:
        self._voxel_cloud_path = voxel_cloud_path
        self._db_path = db_path
        self._user = user
        self._password = password
        self._db = self._load_db()

    def _load_db(self) -> GenesisDB:
        return GenesisDB(db_path=self._db_path, voxel_cloud_path=self._voxel_cloud_path)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connection_id = id(writer) & 0xFFFFFFFF
        salt = os.urandom(20)
        capabilities = (
            CLIENT_LONG_PASSWORD
            | CLIENT_LONG_FLAG
            | CLIENT_PROTOCOL_41
            | CLIENT_SECURE_CONNECTION
            | CLIENT_PLUGIN_AUTH
            | CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA
        )
        handshake = self._build_handshake(capabilities, connection_id, salt)
        writer.write(_pack_packet(handshake, 0))
        await writer.drain()

        try:
            payload = await self._read_packet(reader)
        except Exception:
            writer.close()
            await writer.wait_closed()
            return

        if payload is None:
            writer.close()
            await writer.wait_closed()
            return

        try:
            context = self._parse_handshake_response(payload)
        except Exception as exc:
            writer.write(_pack_packet(_error_packet(str(exc)), 1))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        if context.user != self._user:
            writer.write(_pack_packet(_error_packet("Invalid username", 1045, "28000"), 1))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        auth_ok = self._verify_auth(salt)
        if not auth_ok:
            writer.write(_pack_packet(_error_packet("Access denied", 1045, "28000"), 1))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        sequence_id = 1
        writer.write(_pack_packet(_ok_packet(), sequence_id))
        await writer.drain()

        while True:
            try:
                payload = await self._read_packet(reader)
            except asyncio.IncompleteReadError:
                break
            if not payload:
                break
            command = payload[0]
            if command == 0x01:
                break
            if command != 0x03:
                sequence_id = 0
                writer.write(_pack_packet(_error_packet("Unsupported command"), sequence_id))
                await writer.drain()
                continue

            query = payload[1:].decode("utf-8", errors="replace")
            await self._handle_query(writer, query)

        writer.close()
        await writer.wait_closed()

    async def _handle_query(self, writer: asyncio.StreamWriter, query: str) -> None:
        normalized = query.strip()
        sequence_id = 0
        if not normalized:
            writer.write(_pack_packet(_error_packet("Query must not be empty"), sequence_id))
            await writer.drain()
            return

        lower = normalized.lower()
        if lower.startswith("set "):
            writer.write(_pack_packet(_ok_packet(), sequence_id))
            await writer.drain()
            return

        try:
            sql = normalize_sql(normalized)
        except Exception as exc:
            writer.write(_pack_packet(_error_packet(str(exc)), sequence_id))
            await writer.drain()
            return

        try:
            result = self._db.execute_sql(sql)
        except Exception as exc:
            writer.write(_pack_packet(_error_packet(str(exc)), sequence_id))
            await writer.drain()
            return

        if result.operation != "select":
            writer.write(_pack_packet(_ok_packet(result.affected_rows), sequence_id))
            await writer.drain()
            return

        if not result.columns:
            writer.write(_pack_packet(_ok_packet(), sequence_id))
            await writer.drain()
            return

        writer.write(_pack_packet(_pack_lenenc_int(len(result.columns)), sequence_id))
        await writer.drain()

        column_types = self._infer_column_types(result.columns, result.rows)
        sequence_id = 1
        for name, column_type in zip(result.columns, column_types):
            writer.write(_pack_packet(_column_definition(name, column_type), sequence_id))
            sequence_id += 1
        writer.write(_pack_packet(_eof_packet(), sequence_id))
        sequence_id += 1
        await writer.drain()

        for row in result.rows:
            payload = b"".join(self._format_row_value(row.get(column)) for column in result.columns)
            writer.write(_pack_packet(payload, sequence_id))
            sequence_id += 1
        writer.write(_pack_packet(_eof_packet(), sequence_id))
        await writer.drain()

    def _infer_column_types(self, columns: Iterable[str], rows: list[dict[str, object]]) -> list[int]:
        types: list[int] = []
        for column in columns:
            column_type = MYSQL_TYPE_VAR_STRING
            for row in rows:
                value = row.get(column)
                if value is not None:
                    column_type = _column_type_from_value(value)
                    break
            types.append(column_type)
        return types

    def _format_row_value(self, value: object) -> bytes:
        if value is None:
            return b"\xfb"
        if isinstance(value, (bytes, bytearray)):
            return _pack_lenenc_int(len(value)) + bytes(value)
        return _pack_lenenc_str(str(value))

    def _build_handshake(self, capabilities: int, connection_id: int, salt: bytes) -> bytes:
        auth_plugin_name = b"mysql_native_password"
        part1 = salt[:8]
        part2 = salt[8:]
        payload = [
            struct.pack("B", 10),
            SERVER_VERSION.encode("utf-8") + b"\x00",
            struct.pack("<I", connection_id),
            part1,
            b"\x00",
            struct.pack("<H", capabilities & 0xFFFF),
            struct.pack("B", 0x21),
            struct.pack("<H", 2),
            struct.pack("<H", (capabilities >> 16) & 0xFFFF),
            struct.pack("B", len(salt) + 1),
            b"\x00" * 10,
            part2 + b"\x00",
            auth_plugin_name + b"\x00",
        ]
        return b"".join(payload)

    def _parse_handshake_response(self, payload: bytes) -> ClientContext:
        capabilities = int.from_bytes(payload[0:4], "little")
        offset = 4 + 4 + 1 + 23
        username, offset = _read_null_terminated(payload, offset)

        auth_response = b""
        if capabilities & CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA:
            length, offset = _read_lenenc_int(payload, offset)
            auth_response = payload[offset:offset + length]
            offset += length
        elif capabilities & CLIENT_SECURE_CONNECTION:
            length = payload[offset]
            offset += 1
            auth_response = payload[offset:offset + length]
            offset += length
        else:
            auth_response, offset = _read_null_bytes(payload, offset)

        if capabilities & CLIENT_CONNECT_WITH_DB:
            _, offset = _read_null_terminated(payload, offset)

        if capabilities & CLIENT_PLUGIN_AUTH:
            _, offset = _read_null_terminated(payload, offset)

        self._last_auth_response = auth_response
        return ClientContext(user=username, capabilities=capabilities)

    def _verify_auth(self, salt: bytes) -> bool:
        if not self._password:
            return True
        auth_response = getattr(self, "_last_auth_response", b"")
        if not auth_response:
            return False
        expected = _scramble_password(self._password, salt)
        return auth_response == expected

    async def _read_packet(self, reader: asyncio.StreamReader) -> Optional[bytes]:
        header = await reader.readexactly(4)
        length = int.from_bytes(header[:3], "little")
        if length == 0:
            return b""
        payload = await reader.readexactly(length)
        return payload


async def serve_mysql_gateway(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    voxel_cloud_path: Optional[str] = DEFAULT_VOXEL_CLOUD_PATH,
    db_path: str = DEFAULT_DB_PATH,
    user: str = DEFAULT_USER,
    password: str = DEFAULT_PASSWORD,
) -> None:
    gateway = MySQLGateway(
        voxel_cloud_path=voxel_cloud_path,
        db_path=db_path,
        user=user,
        password=password,
    )
    server = await asyncio.start_server(gateway.handle_client, host, port)

    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    LOGGER.info("Genesis MySQL gateway listening on %s", addresses)

    async with server:
        await server.serve_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve_mysql_gateway())


if __name__ == "__main__":
    main()

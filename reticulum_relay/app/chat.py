from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.normalizer import NormalizedMessage


class ChatStore:
    """Durable, queryable LXMF conversation history."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    destination_hash TEXT PRIMARY KEY,
                    display_name TEXT,
                    last_message TEXT NOT NULL DEFAULT '',
                    last_activity INTEGER NOT NULL,
                    unread_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_hash TEXT NOT NULL UNIQUE,
                    client_token TEXT UNIQUE,
                    conversation_hash TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    text TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    message_timestamp INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    delivery_method TEXT,
                    progress REAL NOT NULL DEFAULT 0,
                    error TEXT,
                    signature_validated INTEGER,
                    transport_encrypted INTEGER,
                    transport_encryption TEXT,
                    rssi REAL,
                    snr REAL,
                    quality REAL,
                    raw_lxmf BLOB,
                    FOREIGN KEY(conversation_hash)
                        REFERENCES chat_conversations(destination_hash)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS chat_messages_conversation_id
                    ON chat_messages(conversation_hash, id DESC);

                CREATE TABLE IF NOT EXISTS reticulum_announces (
                    destination_hash TEXT PRIMARY KEY,
                    identity_hash TEXT,
                    aspect TEXT NOT NULL,
                    display_name TEXT,
                    app_data_text TEXT,
                    first_seen INTEGER NOT NULL,
                    received_at INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    hops INTEGER,
                    announce_packet_hash TEXT,
                    is_path_response INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS reticulum_announces_received
                    ON reticulum_announces(received_at DESC);
                """
            )

    @staticmethod
    def _serialize(message: Any) -> bytes | None:
        try:
            return bytes(message.packed_container())
        except Exception:
            return None

    def record_inbound(self, message: NormalizedMessage, raw_message: Any) -> dict[str, Any]:
        created_at = int(time.time())
        timestamp = message.timestamp or created_at
        raw = self._serialize(raw_message)
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM chat_messages WHERE message_hash = ?", (message.message_id,)
            ).fetchone()
            if existing:
                return self._message_dict(existing)
            connection.execute(
                """
                INSERT INTO chat_conversations (
                    destination_hash, display_name, last_message, last_activity, unread_count
                ) VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(destination_hash) DO UPDATE SET
                    display_name = COALESCE(excluded.display_name, chat_conversations.display_name),
                    last_message = excluded.last_message,
                    last_activity = excluded.last_activity,
                    unread_count = chat_conversations.unread_count + 1
                """,
                (message.source_hash, message.sender_name, message.text or message.title, created_at),
            )
            connection.execute(
                """
                INSERT INTO chat_messages (
                    message_hash, conversation_hash, direction, text, title,
                    message_timestamp, created_at, state, delivery_method, progress,
                    signature_validated, transport_encrypted, transport_encryption,
                    rssi, snr, quality, raw_lxmf
                ) VALUES (?, ?, 'inbound', ?, ?, ?, ?, 'received', ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.source_hash,
                    message.text,
                    message.title,
                    timestamp,
                    created_at,
                    self._method_name(getattr(raw_message, "method", None)),
                    self._bool_or_none(getattr(raw_message, "signature_validated", None)),
                    self._bool_or_none(getattr(raw_message, "transport_encrypted", None)),
                    getattr(raw_message, "transport_encryption", None),
                    getattr(raw_message, "rssi", None),
                    getattr(raw_message, "snr", None),
                    getattr(raw_message, "q", None),
                    raw,
                ),
            )
            row = connection.execute(
                "SELECT * FROM chat_messages WHERE message_hash = ?", (message.message_id,)
            ).fetchone()
        return self._message_dict(row)

    def record_outbound(
        self,
        raw_message: Any,
        destination_hash: str,
        text: str,
        title: str,
        state: str,
        method: str,
        client_token: str | None = None,
    ) -> dict[str, Any]:
        created_at = int(time.time())
        timestamp = int(getattr(raw_message, "timestamp", 0) or created_at)
        message_hash = self._hex(getattr(raw_message, "hash", None))
        if not message_hash:
            message_hash = self._hex(getattr(raw_message, "message_id", None))
        raw = self._serialize(raw_message)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO chat_conversations (
                    destination_hash, display_name, last_message, last_activity, unread_count
                ) VALUES (?, NULL, ?, ?, 0)
                ON CONFLICT(destination_hash) DO UPDATE SET
                    last_message = excluded.last_message,
                    last_activity = excluded.last_activity
                """,
                (destination_hash, text or title, created_at),
            )
            connection.execute(
                """
                INSERT INTO chat_messages (
                    message_hash, client_token, conversation_hash, direction, text, title,
                    message_timestamp, created_at, state, delivery_method, progress,
                    transport_encrypted, transport_encryption, raw_lxmf
                ) VALUES (?, ?, ?, 'outbound', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_hash) DO UPDATE SET
                    state = excluded.state,
                    progress = excluded.progress,
                    raw_lxmf = COALESCE(excluded.raw_lxmf, chat_messages.raw_lxmf)
                """,
                (
                    message_hash,
                    client_token or None,
                    destination_hash,
                    text,
                    title,
                    timestamp,
                    created_at,
                    state,
                    method,
                    float(getattr(raw_message, "progress", 0) or 0),
                    self._bool_or_none(getattr(raw_message, "transport_encrypted", None)),
                    getattr(raw_message, "transport_encryption", None),
                    raw,
                ),
            )
            row = connection.execute(
                "SELECT * FROM chat_messages WHERE message_hash = ?", (message_hash,)
            ).fetchone()
        return self._message_dict(row)

    def update_outbound(self, raw_message: Any, state: str, error: str | None = None) -> None:
        message_hash = self._hex(getattr(raw_message, "hash", None))
        if not message_hash:
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE chat_messages
                SET state = ?, progress = ?, error = ?, delivery_method = ?,
                    transport_encrypted = ?, transport_encryption = ?, raw_lxmf = ?
                WHERE message_hash = ?
                """,
                (
                    state,
                    float(getattr(raw_message, "progress", 0) or 0),
                    error,
                    self._method_name(getattr(raw_message, "method", None)),
                    self._bool_or_none(getattr(raw_message, "transport_encrypted", None)),
                    getattr(raw_message, "transport_encryption", None),
                    self._serialize(raw_message),
                    message_hash,
                ),
            )

    def conversations(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 500)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.destination_hash,
                       COALESCE(a.display_name, c.display_name) AS display_name,
                       c.last_message, c.last_activity, c.unread_count
                FROM chat_conversations c
                LEFT JOIN reticulum_announces a
                    ON a.destination_hash = c.destination_hash
                    AND a.aspect = 'lxmf.delivery'
                ORDER BY c.last_activity DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "index": index,
                "destination_hash": row["destination_hash"],
                "display_name": row["display_name"] or row["destination_hash"][:12],
                "last_text": row["last_message"],
                "timestamp": row["last_activity"],
                "unread_count": row["unread_count"],
            }
            for index, row in enumerate(rows, 1)
        ]

    def messages(
        self, destination_hash: str, limit: int = 100, before_id: int | None = None
    ) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 250)
        sql = "SELECT * FROM chat_messages WHERE conversation_hash = ?"
        params: list[Any] = [destination_hash]
        if before_id is not None:
            sql += " AND id < ?"
            params.append(int(before_id))
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._message_dict(row) for row in reversed(rows)]

    def message(self, message_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM chat_messages WHERE message_hash = ?", (message_hash,)
            ).fetchone()
        return self._message_dict(row) if row else None

    def display_name_for_destination(self, destination_hash: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(a.display_name, c.display_name) AS display_name
                FROM (SELECT ? AS destination_hash) wanted
                LEFT JOIN chat_conversations c
                    ON c.destination_hash = wanted.destination_hash
                LEFT JOIN reticulum_announces a
                    ON a.destination_hash = wanted.destination_hash
                    AND a.aspect = 'lxmf.delivery'
                """,
                (destination_hash,),
            ).fetchone()
        if not row or not row["display_name"]:
            return None
        return str(row["display_name"])

    def message_for_token(self, client_token: str) -> dict[str, Any] | None:
        if not client_token:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM chat_messages WHERE client_token = ?", (client_token,)
            ).fetchone()
        return self._message_dict(row) if row else None

    def mark_read(self, destination_hash: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE chat_conversations SET unread_count = 0 WHERE destination_hash = ?",
                (destination_hash,),
            )

    def record_announce(
        self,
        destination_hash: str,
        identity_hash: str | None,
        aspect: str,
        display_name: str | None,
        app_data_text: str | None,
        hops: int | None,
        announce_packet_hash: str | None,
        is_path_response: bool,
    ) -> dict[str, Any]:
        received_at = int(time.time())
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reticulum_announces (
                    destination_hash, identity_hash, aspect, display_name, app_data_text,
                    first_seen, received_at, seen_count, hops, announce_packet_hash,
                    is_path_response
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(destination_hash) DO UPDATE SET
                    identity_hash = COALESCE(excluded.identity_hash, reticulum_announces.identity_hash),
                    aspect = excluded.aspect,
                    display_name = COALESCE(excluded.display_name, reticulum_announces.display_name),
                    app_data_text = COALESCE(excluded.app_data_text, reticulum_announces.app_data_text),
                    received_at = excluded.received_at,
                    seen_count = reticulum_announces.seen_count + 1,
                    hops = excluded.hops,
                    announce_packet_hash = excluded.announce_packet_hash,
                    is_path_response = excluded.is_path_response
                """,
                (
                    destination_hash,
                    identity_hash,
                    aspect,
                    display_name,
                    app_data_text,
                    received_at,
                    received_at,
                    hops,
                    announce_packet_hash,
                    int(is_path_response),
                ),
            )
            connection.execute(
                """
                DELETE FROM reticulum_announces
                WHERE destination_hash IN (
                    SELECT destination_hash FROM reticulum_announces
                    ORDER BY received_at DESC, destination_hash
                    LIMIT -1 OFFSET 5000
                )
                """
            )
            row = connection.execute(
                "SELECT * FROM reticulum_announces WHERE destination_hash = ?",
                (destination_hash,),
            ).fetchone()
        return self._announce_dict(row)

    def announces(self, limit: int = 100, aspect: str | None = None) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 500)
        sql = "SELECT * FROM reticulum_announces"
        params: list[Any] = []
        if aspect:
            sql += " WHERE aspect = ?"
            params.append(aspect)
        sql += " ORDER BY received_at DESC, destination_hash LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._announce_dict(row) for row in rows]

    @staticmethod
    def _message_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "message_hash": row["message_hash"],
            "client_token": row["client_token"],
            "conversation_hash": row["conversation_hash"],
            "direction": row["direction"],
            "text": row["text"],
            "title": row["title"],
            "timestamp": row["message_timestamp"],
            "created_at": row["created_at"],
            "state": row["state"],
            "delivery_method": row["delivery_method"],
            "progress": row["progress"],
            "error": row["error"],
            "signature_validated": ChatStore._db_bool(row["signature_validated"]),
            "transport_encrypted": ChatStore._db_bool(row["transport_encrypted"]),
            "transport_encryption": row["transport_encryption"],
            "rssi": row["rssi"],
            "snr": row["snr"],
            "quality": row["quality"],
        }

    @staticmethod
    def _announce_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "destination_hash": row["destination_hash"],
            "identity_hash": row["identity_hash"],
            "aspect": row["aspect"],
            "display_name": row["display_name"],
            "app_data_text": row["app_data_text"],
            "first_seen": row["first_seen"],
            "received_at": row["received_at"],
            "seen_count": row["seen_count"],
            "hops": row["hops"],
            "announce_packet_hash": row["announce_packet_hash"],
            "is_path_response": bool(row["is_path_response"]),
        }

    @staticmethod
    def _hex(value: Any) -> str:
        return value.hex() if isinstance(value, bytes) else str(value or "")

    @staticmethod
    def _bool_or_none(value: Any) -> int | None:
        return None if value is None else int(bool(value))

    @staticmethod
    def _db_bool(value: Any) -> bool | None:
        return None if value is None else bool(value)

    @staticmethod
    def _method_name(value: Any) -> str | None:
        return {1: "opportunistic", 2: "direct", 3: "propagated", 5: "paper"}.get(value)

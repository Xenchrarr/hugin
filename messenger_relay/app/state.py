from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any


class StateStore:
    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS relay_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    thread_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    last_sender TEXT,
                    last_text TEXT,
                    timestamp INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS reply_context (
                    phone TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL
                );
                """
            )

    def get_value(self, key: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM relay_kv WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_value(self, key: str, value: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO relay_kv (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def upsert_conversation(
        self,
        thread_id: str,
        room_id: str,
        title: str,
        last_sender: str | None = None,
        last_text: str | None = None,
        timestamp: int = 0,
    ) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO conversations
                    (thread_id, room_id, title, last_sender, last_text, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (thread_id) DO UPDATE SET
                    room_id = excluded.room_id,
                    title = excluded.title,
                    last_sender = COALESCE(excluded.last_sender, conversations.last_sender),
                    last_text = COALESCE(excluded.last_text, conversations.last_text),
                    timestamp = MAX(excluded.timestamp, conversations.timestamp)
                """,
                (thread_id, room_id, title, last_sender, last_text, timestamp),
            )

    def conversations(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT thread_id, room_id, title, last_sender, last_text, timestamp "
                "FROM conversations ORDER BY timestamp DESC, title LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) | {"index": index} for index, row in enumerate(rows, 1)]

    def room_for_thread(self, thread_id: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT room_id FROM conversations WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return str(row["room_id"]) if row else None

    def set_context(self, phone: str, thread_id: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO reply_context (phone, thread_id) VALUES (?, ?) "
                "ON CONFLICT (phone) DO UPDATE SET thread_id = excluded.thread_id",
                (phone, thread_id),
            )

    def get_context(self, phone: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                """
                SELECT c.thread_id, c.room_id, c.title
                FROM reply_context r
                JOIN conversations c ON c.thread_id = r.thread_id
                WHERE r.phone = ?
                """,
                (phone,),
            ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        with self._lock:
            self._db.close()

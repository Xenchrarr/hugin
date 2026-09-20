"""Persistent duplicate suppression for physical SMS/MMS dispatches."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DispatchDecision:
    state: str
    response: dict | None = None
    error: str | None = None


class DispatchTokenConflict(ValueError):
    pass


class DeliveryLedger:
    """SQLite receipt ledger which survives sms-hub container restarts."""

    def __init__(
        self,
        path: str,
        *,
        stale_after_seconds: int = 600,
        retention_days: int = 30,
    ) -> None:
        self.path = path
        self.stale_after_seconds = max(60, int(stale_after_seconds))
        self.retention_days = max(1, int(retention_days))
        self._lock = threading.RLock()
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS dispatch_receipts ("
                " token TEXT PRIMARY KEY,"
                " fingerprint TEXT NOT NULL,"
                " kind TEXT NOT NULL,"
                " status TEXT NOT NULL CHECK (status IN "
                "   ('sending', 'accepted', 'failed', 'uncertain')) ,"
                " response_json TEXT,"
                " error TEXT,"
                " created_at REAL NOT NULL,"
                " updated_at REAL NOT NULL"
                ")"
            )
            cutoff = time.time() - self.retention_days * 86400
            connection.execute(
                "DELETE FROM dispatch_receipts "
                "WHERE status IN ('accepted', 'failed') AND updated_at < ?",
                (cutoff,),
            )

    def begin(self, token: str, fingerprint: str, kind: str) -> DispatchDecision:
        now = time.time()
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT fingerprint, kind, status, response_json, error, updated_at "
                "FROM dispatch_receipts WHERE token = ?",
                (token,),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO dispatch_receipts "
                    "(token, fingerprint, kind, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'sending', ?, ?)",
                    (token, fingerprint, kind, now, now),
                )
                return DispatchDecision("send")

            if row["fingerprint"] != fingerprint or row["kind"] != kind:
                raise DispatchTokenConflict(
                    "delivery_token was already used for different message content"
                )

            status = str(row["status"])
            if status == "accepted":
                response = json.loads(row["response_json"] or "{}")
                return DispatchDecision("accepted", response=response)
            if status == "uncertain":
                return DispatchDecision("uncertain", error=row["error"])
            if status == "sending":
                age = now - float(row["updated_at"])
                if age < self.stale_after_seconds:
                    return DispatchDecision("in_progress")
                error = "gateway restarted or timed out while delivery was in progress"
                connection.execute(
                    "UPDATE dispatch_receipts SET status = 'uncertain', error = ?, "
                    "updated_at = ? WHERE token = ?",
                    (error, now, token),
                )
                return DispatchDecision("uncertain", error=error)

            # A definite failure is safe to retry with the same stable token.
            connection.execute(
                "UPDATE dispatch_receipts SET status = 'sending', response_json = NULL, "
                "error = NULL, updated_at = ? WHERE token = ?",
                (now, token),
            )
            return DispatchDecision("send")

    def mark_accepted(self, token: str, response: dict) -> None:
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE dispatch_receipts SET status = 'accepted', response_json = ?, "
                "error = NULL, updated_at = ? WHERE token = ? AND status = 'sending'",
                (json.dumps(response, separators=(",", ":")), time.time(), token),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("dispatch receipt was not in sending state")

    def mark_failed(self, token: str, error: str, *, uncertain: bool) -> None:
        status = "uncertain" if uncertain else "failed"
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE dispatch_receipts SET status = ?, error = ?, updated_at = ? "
                "WHERE token = ? AND status = 'sending'",
                (status, error[:2000], time.time(), token),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("dispatch receipt was not in sending state")


def ledger_from_environment() -> DeliveryLedger:
    return DeliveryLedger(
        os.environ.get(
            "SMS_DELIVERY_LEDGER_PATH",
            "/data/sms-delivery-ledger.sqlite3",
        ),
        stale_after_seconds=int(
            os.environ.get("SMS_DELIVERY_STALE_SECONDS", "600")
        ),
        retention_days=int(os.environ.get("SMS_DELIVERY_RECEIPT_RETENTION_DAYS", "30")),
    )

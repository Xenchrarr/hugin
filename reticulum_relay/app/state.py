from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {
            "contacts": {},
            "contexts": {},
            "delivery_tokens": {},
        }
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in self._data:
                    if isinstance(raw.get(key), dict):
                        self._data[key] = raw[key]
        except FileNotFoundError:
            return

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self._path)

    def remember_contact(
        self, destination_hash: str, display_name: str | None, text: str = ""
    ) -> None:
        with self._lock:
            existing = self._data["contacts"].get(destination_hash, {})
            self._data["contacts"][destination_hash] = {
                "destination_hash": destination_hash,
                "display_name": display_name or existing.get("display_name") or destination_hash[:12],
                "last_text": text[:80],
                "timestamp": int(time.time()),
            }
            self._save()

    def contacts(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            contacts = [dict(item) for item in self._data["contacts"].values()]
        contacts.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
        return [{"index": index, **item} for index, item in enumerate(contacts[:limit], 1)]

    def remember_contact_name(self, destination_hash: str, display_name: str) -> None:
        """Apply newly learned announce metadata without creating an empty contact."""
        with self._lock:
            existing = self._data["contacts"].get(destination_hash)
            if (
                not existing
                or not display_name
                or existing.get("display_name") == display_name
            ):
                return
            existing["display_name"] = display_name
            self._save()

    def set_context(self, phone: str, destination_hash: str) -> None:
        with self._lock:
            self._data["contexts"][phone] = destination_hash
            self._save()

    def get_context(self, phone: str) -> dict[str, Any] | None:
        with self._lock:
            destination_hash = self._data["contexts"].get(phone)
            if not destination_hash:
                return None
            contact = self._data["contacts"].get(destination_hash, {})
            return {
                "destination_hash": destination_hash,
                "display_name": contact.get("display_name") or destination_hash[:12],
            }

    def delivery_result(self, token: str) -> str | None:
        with self._lock:
            result = self._data["delivery_tokens"].get(token)
            return str(result) if result else None

    def record_delivery(self, token: str, message_id: str) -> None:
        if not token:
            return
        with self._lock:
            self._data["delivery_tokens"][token] = message_id
            # Bound this cache without coupling it to Message Hub retention.
            while len(self._data["delivery_tokens"]) > 10000:
                oldest = next(iter(self._data["delivery_tokens"]))
                self._data["delivery_tokens"].pop(oldest, None)
            self._save()

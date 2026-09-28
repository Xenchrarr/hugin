from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


def _hex(value: Any) -> str:
    if isinstance(value, bytes):
        return value.hex()
    return str(value or "")


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


@dataclass(frozen=True)
class NormalizedMessage:
    message_id: str
    source_hash: str
    destination_hash: str
    sender_name: str | None
    text: str
    title: str
    timestamp: int
    fields: dict[str, Any]

    def display_text(self) -> str:
        body = self.text or self.title or "<LXMF message>"
        label = self.sender_name or self.source_hash[:12]
        return f"{label}: {body}" if label else body

    def redacted(self, patterns: list[dict[str, str]]) -> "NormalizedMessage":
        import re

        updates: dict[str, Any] = {}
        for item in patterns:
            field = str(item.get("field") or "")
            value = getattr(self, field, None)
            if isinstance(value, str) and item.get("pattern"):
                updates[field] = re.sub(
                    str(item["pattern"]), str(item.get("replace", "[REDACTED]")), value
                )
        return replace(self, **updates) if updates else self


def normalize_lxmf(message: Any) -> NormalizedMessage:
    source_hash = _hex(getattr(message, "source_hash", None))
    destination_hash = _hex(getattr(message, "destination_hash", None))
    message_hash = _hex(getattr(message, "hash", None))
    if not message_hash:
        message_hash = _hex(getattr(message, "message_id", None))
    fields = getattr(message, "fields", None)
    if not isinstance(fields, dict):
        fields = {}
    sender_name = getattr(message, "source_display_name", None)
    return NormalizedMessage(
        message_id=message_hash,
        source_hash=source_hash,
        destination_hash=destination_hash,
        sender_name=_text(sender_name) or None,
        text=_text(getattr(message, "content", None)),
        title=_text(getattr(message, "title", None)),
        timestamp=int(getattr(message, "timestamp", 0) or 0),
        fields=fields,
    )

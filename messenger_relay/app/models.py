from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


@dataclass(frozen=True)
class RoomInfo:
    room_id: str
    thread_id: str
    title: str
    chat_type: str = "unknown"
    members: dict[str, str] | None = None


@dataclass(frozen=True)
class NormalizedMessage:
    message_id: str
    chat_id: str
    chat_title: str | None
    chat_type: str
    sender_id: str | None
    sender_name: str | None
    text: str | None
    media_type: str | None
    caption: str | None
    timestamp: int
    room_id: str

    def redacted(self, patterns: list[dict[str, str]]) -> "NormalizedMessage":
        import re

        updates: dict[str, Any] = {}
        for item in patterns:
            field = item.get("field", "")
            value = getattr(self, field, None)
            if isinstance(value, str) and item.get("pattern"):
                updates[field] = re.sub(
                    item["pattern"], item.get("replace", "[REDACTED]"), value
                )
        return replace(self, **updates) if updates else self

    def to_payload(
        self,
        include_fields: list[str] | None = None,
        exclude_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        data = asdict(self)
        if include_fields:
            return {key: value for key, value in data.items() if key in include_fields}
        if exclude_fields:
            return {key: value for key, value in data.items() if key not in exclude_fields}
        return data

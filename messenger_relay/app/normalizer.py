from __future__ import annotations

from app.models import NormalizedMessage, RoomInfo


class MatrixEventNormalizer:
    """Convert live mautrix-meta portal events into Hugin messages."""

    _MEDIA_TYPES = {
        "m.image": "photo",
        "m.file": "document",
        "m.audio": "audio",
        "m.video": "video",
    }

    def __init__(self, own_user_id: str, bridge_bot_user_id: str, ghost_prefix: str) -> None:
        self._own_user_id = own_user_id
        self._bridge_bot_user_id = bridge_bot_user_id
        self._ghost_prefix = ghost_prefix

    def normalize(self, event: dict, room: RoomInfo) -> NormalizedMessage | None:
        if event.get("type") != "m.room.message":
            return None
        sender = str(event.get("sender") or "")
        if sender in {self._own_user_id, self._bridge_bot_user_id}:
            return None
        # A portal can contain local Matrix users. Only Messenger ghost users
        # represent inbound remote messages.
        if self._ghost_prefix and not sender.startswith(self._ghost_prefix):
            return None

        content = event.get("content") or {}
        msgtype = str(content.get("msgtype") or "")
        body = str(content.get("body") or "").strip()
        text: str | None = None
        media_type: str | None = None
        caption: str | None = None
        if msgtype in {"m.text", "m.emote"}:
            text = body or None
        elif msgtype in self._MEDIA_TYPES:
            media_type = self._MEDIA_TYPES[msgtype]
            caption = body or None
        else:
            return None

        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            return None
        sender_name = (room.members or {}).get(sender)
        sender_id = sender[len(self._ghost_prefix):].split(":", 1)[0] if self._ghost_prefix else sender
        return NormalizedMessage(
            message_id=event_id,
            chat_id=room.thread_id,
            chat_title=room.title or None,
            chat_type=room.chat_type,
            sender_id=sender_id or None,
            sender_name=sender_name,
            text=text,
            media_type=media_type,
            caption=caption,
            timestamp=int(event.get("origin_server_ts") or 0) // 1000,
            room_id=room.room_id,
        )

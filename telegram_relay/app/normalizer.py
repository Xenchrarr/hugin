from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NormalizedMessage:
    message_id: int
    chat_id: int
    chat_title: Optional[str]
    chat_type: str  # "private" | "group" | "unknown"
    sender_id: Optional[int]
    sender_name: Optional[str]
    text: Optional[str]
    media_type: Optional[str]  # None | "photo" | "document"
    media_file_id: Optional[int]  # TDLib file id for downloading (photo/document)
    caption: Optional[str]
    timestamp: int
    raw: dict = field(default_factory=dict)

    def to_payload(
        self,
        include_fields: Optional[list[str]] = None,
        exclude_fields: Optional[list[str]] = None,
    ) -> dict:
        data: dict = {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "chat_type": self.chat_type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "text": self.text,
            "media_type": self.media_type,
            "caption": self.caption,
            "timestamp": self.timestamp,
        }
        if include_fields:
            data = {k: v for k, v in data.items() if k in include_fields}
        elif exclude_fields:
            data = {k: v for k, v in data.items() if k not in exclude_fields}
        return data


class MessageNormalizer:
    def normalize(self, update: dict) -> Optional[NormalizedMessage]:
        message = update.get("message")
        if not message:
            return None

        if message.get("is_outgoing"):
            return None

        content = message.get("content", {})
        content_type = content.get("@type")
        text, media_type, media_file_id, caption = self._extract_content(content, content_type)

        if text is None and media_type is None:
            return None

        sender_id, sender_name = self._extract_sender(message.get("sender_id", {}))

        return NormalizedMessage(
            message_id=message.get("id", 0),
            chat_id=message.get("chat_id", 0),
            chat_title=None,  # enriched by TDLib chat lookup if needed
            chat_type=self._infer_chat_type(message.get("chat_id")),
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            media_type=media_type,
            media_file_id=media_file_id,
            caption=caption,
            timestamp=message.get("date", 0),
            raw=message,
        )

    def _extract_content(
        self, content: dict, content_type: Optional[str]
    ) -> tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
        if content_type == "messageText":
            return content.get("text", {}).get("text"), None, None, None
        if content_type == "messagePhoto":
            cap = content.get("caption", {}).get("text") or None
            sizes = content.get("photo", {}).get("sizes", [])
            file_id = sizes[-1].get("photo", {}).get("id") if sizes else None
            return None, "photo", file_id, cap
        if content_type == "messageDocument":
            cap = content.get("caption", {}).get("text") or None
            file_id = content.get("document", {}).get("document", {}).get("id")
            return None, "document", file_id, cap
        return None, None, None, None

    def _extract_sender(
        self, sender: dict
    ) -> tuple[Optional[int], Optional[str]]:
        sender_type = sender.get("@type")
        if sender_type == "messageSenderUser":
            return sender.get("user_id"), None
        if sender_type == "messageSenderChat":
            return None, None
        return None, None

    def _infer_chat_type(self, chat_id: Optional[int]) -> str:
        if chat_id is None:
            return "unknown"
        return "private" if chat_id > 0 else "group"

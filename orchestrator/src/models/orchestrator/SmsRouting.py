from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SmsConversation:
    id: int
    owner_user_id: int
    service: str
    integration_account: str
    external_chat_id: str
    alias: str
    display_name: str
    available: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_row(row) -> "SmsConversation":
        return SmsConversation(
            id=int(row[0]), owner_user_id=int(row[1]), service=row[2],
            integration_account=row[3], external_chat_id=row[4], alias=row[5],
            display_name=row[6], available=bool(row[7]),
            created_at=row[8], updated_at=row[9],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_user_id": self.owner_user_id,
            "service": self.service,
            "integration_account": self.integration_account,
            "external_chat_id": self.external_chat_id,
            "alias": self.alias,
            "display_name": self.display_name,
            "available": self.available,
        }


@dataclass(frozen=True)
class SmsRoutedMessage:
    id: int
    owner_user_id: int
    conversation_id: int
    reference: int
    direction: str
    body: str
    author: str | None
    external_message_id: str | None
    transport_event_id: str | None
    reply_to_reference: int | None
    send_status: str
    status_detail: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_row(row) -> "SmsRoutedMessage":
        return SmsRoutedMessage(
            id=int(row[0]), owner_user_id=int(row[1]), conversation_id=int(row[2]),
            reference=int(row[3]), direction=row[4], body=row[5], author=row[6],
            external_message_id=row[7], transport_event_id=row[8],
            reply_to_reference=int(row[9]) if row[9] is not None else None,
            send_status=row[10], status_detail=row[11], created_at=row[12], updated_at=row[13],
        )


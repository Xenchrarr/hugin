from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.persistence.SmsRoutingStorage import SmsRoutingStorage


_ALIAS_RE = re.compile(r"^[a-z][a-z0-9_-]{0,9}/[a-z0-9][a-z0-9_-]{0,17}$")
_STATUSES = {"accepted", "queued", "failed", "uncertain"}


class SmsRoutingService:
    """Conversation routing rules independent of SMS and integration transports."""

    def __init__(self, storage: SmsRoutingStorage | None = None):
        if storage is None:
            from src.persistence.SmsRoutingStorage import SmsRoutingStorage
            storage = SmsRoutingStorage()
        self.storage = storage

    @staticmethod
    def normalize_alias(alias: str) -> str:
        value = str(alias or "").strip().lower()
        if not _ALIAS_RE.fullmatch(value):
            raise ValueError(
                "alias must look like tg/nikolai, use letters, digits, _ or -, and be at most 29 characters"
            )
        return value

    def register_external_message(
        self, *, owner_user_id: int, service: str, integration_account: str,
        external_chat_id: str, alias: str, display_name: str, event_id: str,
        external_message_id: str | None, body: str, author: str | None = None,
    ) -> dict:
        service = str(service or "").strip().lower()
        account = str(integration_account or "").strip()
        chat_id = str(external_chat_id or "").strip()
        event_id = str(event_id or "").strip()
        body = str(body or "")
        alias = self.normalize_alias(alias)
        if not service or not account or not chat_id or not event_id:
            raise ValueError("service, integration_account, external_chat_id and event_id are required")
        if alias.split("/", 1)[0] != service:
            raise ValueError("alias service prefix must match service")
        if not body.strip():
            raise ValueError("message body is empty")

        conversation = self.storage.get_or_create_conversation(
            owner_user_id=owner_user_id, service=service,
            integration_account=account, external_chat_id=chat_id,
            alias=alias, display_name=str(display_name or alias).strip()[:200] or alias,
        )
        existing = self.storage.get_message_by_event(owner_user_id, "inbound", event_id)
        duplicate = existing is not None
        message = existing or self.storage.create_message(
            owner_user_id=owner_user_id, conversation_id=conversation.id,
            direction="inbound", body=body, author=(str(author).strip()[:200] if author else None),
            external_message_id=(str(external_message_id) if external_message_id is not None else None),
            transport_event_id=event_id, send_status="received",
        )
        # The persisted identity wins if a later display title generates another alias.
        conversation = self.storage.get_conversation(owner_user_id, message.conversation_id) or conversation
        content = f"{message.author}: {message.body}" if message.author else message.body
        return {
            "duplicate": duplicate,
            "reference": message.reference,
            "alias": conversation.alias,
            "display_name": conversation.display_name,
            "text": f"({conversation.alias} #{message.reference})\n{content}",
        }

    def prepare_outbound(
        self, *, owner_user_id: int, selector_type: str, selector: str | int,
        body: str, event_id: str | None = None,
    ) -> dict:
        body = str(body or "")
        if not body.strip():
            raise ValueError("message body is empty")
        existing = self.storage.get_message_by_event(owner_user_id, "outbound", event_id)
        if existing:
            conversation = self.storage.get_conversation(owner_user_id, existing.conversation_id)
            return self._route_dict(conversation, existing, duplicate=True)

        reply_to_reference = None
        reply_to_external_message_id = None
        if selector_type == "reference":
            try:
                reference = int(selector)
            except (TypeError, ValueError):
                raise ValueError("invalid reply reference")
            original = self.storage.get_message_by_reference(owner_user_id, reference)
            if original is None:
                raise LookupError(f"unknown reply reference #{reference}")
            conversation = self.storage.get_conversation(owner_user_id, original.conversation_id)
            reply_to_reference = reference
            reply_to_external_message_id = original.external_message_id
        elif selector_type == "alias":
            alias = self.normalize_alias(str(selector))
            conversation = self.storage.get_conversation_by_alias(owner_user_id, alias)
            if conversation is None:
                raise LookupError(f"unknown conversation alias {alias}")
        else:
            raise ValueError("selector_type must be alias or reference")

        if conversation is None:
            raise LookupError("conversation is unavailable")
        message = self.storage.create_message(
            owner_user_id=owner_user_id, conversation_id=conversation.id,
            direction="outbound", body=body, transport_event_id=event_id,
            reply_to_reference=reply_to_reference, send_status="prepared",
        )
        result = self._route_dict(conversation, message, duplicate=False)
        result["reply_to_external_message_id"] = reply_to_external_message_id
        return result

    @staticmethod
    def _route_dict(conversation, message, *, duplicate: bool) -> dict:
        return {
            "duplicate": duplicate,
            "reference": message.reference,
            "status": message.send_status,
            "status_detail": message.status_detail,
            "alias": conversation.alias,
            "display_name": conversation.display_name,
            "service": conversation.service,
            "integration_account": conversation.integration_account,
            "external_chat_id": conversation.external_chat_id,
            "available": conversation.available,
            "body": message.body,
            "external_message_id": message.external_message_id,
        }

    def update_status(
        self, *, owner_user_id: int, reference: int, status: str,
        detail: str | None = None, external_message_id: str | None = None,
    ) -> dict:
        if status not in _STATUSES:
            raise ValueError("invalid send status")
        message = self.storage.update_status(
            owner_user_id, reference, status, detail, external_message_id
        )
        if message is None:
            raise LookupError(f"unknown reply reference #{reference}")
        return {"reference": reference, "status": status}

    def list_chats(self, owner_user_id: int, limit: int = 10, offset: int = 0) -> dict:
        limit = min(max(int(limit), 1), 10)
        offset = max(int(offset), 0)
        chats = self.storage.list_conversations(owner_user_id, limit + 1, offset)
        more = len(chats) > limit
        return {
            "chats": [chat.to_dict() for chat in chats[:limit]],
            "more": more,
            "next_offset": offset + limit if more else None,
        }

    def history(
        self, owner_user_id: int, alias: str, limit: int = 5,
        before_reference: int | None = None,
    ) -> dict:
        alias = self.normalize_alias(alias)
        conversation = self.storage.get_conversation_by_alias(owner_user_id, alias)
        if conversation is None:
            raise LookupError(f"unknown conversation alias {alias}")
        limit = min(max(int(limit), 1), 5)
        messages = self.storage.history(owner_user_id, conversation.id, limit + 1, before_reference)
        more = len(messages) > limit
        visible = list(reversed(messages[:limit]))
        items = [{
            "reference": item.reference,
            "direction": item.direction,
            "body": (item.body.replace("\r", "").replace("\n", " / ")[:96] +
                     (">" if len(item.body.replace("\r", "").replace("\n", " / ")) > 96 else "")),
            "author": item.author,
            "status": item.send_status,
        } for item in visible]
        return {
            "alias": conversation.alias,
            "display_name": conversation.display_name,
            "messages": items,
            "more": more,
            "before_reference": min((item.reference for item in messages[:limit]), default=None) if more else None,
        }

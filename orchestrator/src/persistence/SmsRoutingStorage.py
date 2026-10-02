from __future__ import annotations

from src.models.orchestrator.SmsRouting import SmsConversation, SmsRoutedMessage
from src.persistence.JobDb import JobDb


_CONVERSATION_COLUMNS = (
    "id, owner_user_id, service, integration_account, external_chat_id, alias, "
    "display_name, available, created_at, updated_at"
)
_MESSAGE_COLUMNS = (
    "id, owner_user_id, conversation_id, reference, direction, body, author, "
    "external_message_id, transport_event_id, reply_to_reference, send_status, "
    "status_detail, created_at, updated_at"
)


class SmsRoutingStorage:
    """PostgreSQL persistence for stable conversations and account-scoped refs."""

    def __init__(self):
        self._db = JobDb.instance()

    def get_or_create_conversation(
        self, *, owner_user_id: int, service: str, integration_account: str,
        external_chat_id: str, alias: str, display_name: str,
    ) -> SmsConversation:
        try:
            row = self._db.execute(
                "INSERT INTO sms_routing_conversations "
                "(owner_user_id, service, integration_account, external_chat_id, alias, display_name) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (owner_user_id, service, integration_account, external_chat_id) "
                "DO UPDATE SET display_name = EXCLUDED.display_name, available = TRUE, updated_at = NOW() "
                "RETURNING " + _CONVERSATION_COLUMNS,
                (owner_user_id, service, integration_account, external_chat_id, alias, display_name),
            ).fetchone()
            self._db.commit()
            return SmsConversation.from_row(row)
        except Exception:
            self._db.rollback()
            raise

    def get_conversation_by_alias(self, owner_user_id: int, alias: str) -> SmsConversation | None:
        row = self._db.execute(
            f"SELECT {_CONVERSATION_COLUMNS} FROM sms_routing_conversations "
            "WHERE owner_user_id = %s AND alias = %s",
            (owner_user_id, alias),
        ).fetchone()
        return SmsConversation.from_row(row) if row else None

    def get_conversation(self, owner_user_id: int, conversation_id: int) -> SmsConversation | None:
        row = self._db.execute(
            f"SELECT {_CONVERSATION_COLUMNS} FROM sms_routing_conversations "
            "WHERE owner_user_id = %s AND id = %s",
            (owner_user_id, conversation_id),
        ).fetchone()
        return SmsConversation.from_row(row) if row else None

    def list_conversations(self, owner_user_id: int, limit: int = 10, offset: int = 0) -> list[SmsConversation]:
        rows = self._db.execute(
            f"SELECT {_CONVERSATION_COLUMNS} FROM sms_routing_conversations "
            "WHERE owner_user_id = %s ORDER BY alias LIMIT %s OFFSET %s",
            (owner_user_id, limit, offset),
        ).fetchall()
        return [SmsConversation.from_row(row) for row in rows]

    def get_message_by_reference(self, owner_user_id: int, reference: int) -> SmsRoutedMessage | None:
        row = self._db.execute(
            f"SELECT {_MESSAGE_COLUMNS} FROM sms_routing_messages "
            "WHERE owner_user_id = %s AND reference = %s",
            (owner_user_id, reference),
        ).fetchone()
        return SmsRoutedMessage.from_row(row) if row else None

    def get_message_by_event(
        self, owner_user_id: int, direction: str, event_id: str | None
    ) -> SmsRoutedMessage | None:
        if not event_id:
            return None
        row = self._db.execute(
            f"SELECT {_MESSAGE_COLUMNS} FROM sms_routing_messages "
            "WHERE owner_user_id = %s AND direction = %s AND transport_event_id = %s",
            (owner_user_id, direction, event_id),
        ).fetchone()
        return SmsRoutedMessage.from_row(row) if row else None

    def _allocate_reference(self, owner_user_id: int) -> int:
        row = self._db.execute(
            "INSERT INTO sms_routing_reference_counters (owner_user_id, next_reference) "
            "VALUES (%s, 2) ON CONFLICT (owner_user_id) DO UPDATE SET "
            "next_reference = sms_routing_reference_counters.next_reference + 1 "
            "RETURNING next_reference - 1",
            (owner_user_id,),
        ).fetchone()
        return int(row[0])

    def create_message(
        self, *, owner_user_id: int, conversation_id: int, direction: str,
        body: str, author: str | None = None, external_message_id: str | None = None,
        transport_event_id: str | None = None, reply_to_reference: int | None = None,
        send_status: str,
    ) -> SmsRoutedMessage:
        try:
            reference = self._allocate_reference(owner_user_id)
            conflict = (
                " ON CONFLICT (owner_user_id, direction, transport_event_id) "
                "WHERE transport_event_id IS NOT NULL DO UPDATE SET "
                "transport_event_id = EXCLUDED.transport_event_id"
                if transport_event_id else ""
            )
            row = self._db.execute(
                "INSERT INTO sms_routing_messages "
                "(owner_user_id, conversation_id, reference, direction, body, author, "
                "external_message_id, transport_event_id, reply_to_reference, send_status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)" +
                conflict + " RETURNING " + _MESSAGE_COLUMNS,
                (owner_user_id, conversation_id, reference, direction, body, author,
                 external_message_id, transport_event_id, reply_to_reference, send_status),
            ).fetchone()
            self._db.commit()
            return SmsRoutedMessage.from_row(row)
        except Exception:
            self._db.rollback()
            raise

    def update_status(
        self, owner_user_id: int, reference: int, status: str,
        detail: str | None = None, external_message_id: str | None = None,
    ) -> SmsRoutedMessage | None:
        row = self._db.execute(
            "UPDATE sms_routing_messages SET send_status = %s, status_detail = %s, "
            "external_message_id = COALESCE(%s, external_message_id), updated_at = NOW() "
            "WHERE owner_user_id = %s AND reference = %s RETURNING " + _MESSAGE_COLUMNS,
            (status, detail, external_message_id, owner_user_id, reference),
        ).fetchone()
        self._db.commit()
        return SmsRoutedMessage.from_row(row) if row else None

    def history(
        self, owner_user_id: int, conversation_id: int, limit: int = 5,
        before_reference: int | None = None,
    ) -> list[SmsRoutedMessage]:
        params: list = [owner_user_id, conversation_id]
        before = ""
        if before_reference is not None:
            before = " AND reference < %s"
            params.append(before_reference)
        params.append(limit)
        rows = self._db.execute(
            f"SELECT {_MESSAGE_COLUMNS} FROM sms_routing_messages "
            "WHERE owner_user_id = %s AND conversation_id = %s" + before +
            " ORDER BY reference DESC LIMIT %s",
            tuple(params),
        ).fetchall()
        return [SmsRoutedMessage.from_row(row) for row in rows]

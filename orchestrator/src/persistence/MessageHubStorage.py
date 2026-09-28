from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from src.models.orchestrator.MessageHub import (
    HubMessage,
    MessageAttachment,
    MessageDelivery,
    MessageGateway,
)
from src.persistence.JobDb import JobDb


_GATEWAY_COLUMNS = (
    "id, key, name, type, enabled, status, config, consecutive_failures, "
    "consecutive_successes, last_error, last_checked_at, last_healthy_at, "
    "created_at, updated_at"
)

_MESSAGE_COLUMNS = (
    "id, direction, kind, source_gateway_id, source_endpoint_id, external_id, "
    "conversation_key, payload, metadata, priority, idempotency_key, created_at, expires_at"
)

_ATTACHMENT_COLUMNS = (
    "id, message_id, position, content_type, filename, content, size_bytes, sha256, created_at"
)

_DELIVERY_COLUMNS = (
    "id, message_id, gateway_id, target_endpoint_id, route_id, address, payload, "
    "status, recovery_policy, priority, attempts, max_attempts, available_at, "
    "lease_token, leased_until, accepted_at, expired_at, recovery_notified_at, "
    "last_error, idempotency_key, dispatch_token, created_at, updated_at, recipient_key, acknowledged_at"
)

_DELIVERY_WITH_GATEWAY_COLUMNS = (
    ", ".join(f"delivery.{column.strip()}" for column in _DELIVERY_COLUMNS.split(","))
    + ", gateway.key, gateway.type, gateway.config"
)

_SOURCE_TYPE_SQL = "COALESCE(NULLIF(message.metadata->>'source_type', ''), 'other')"
_SOURCE_LABEL_SQL = (
    "COALESCE(NULLIF(message.metadata->>'source_label', ''), "
    "NULLIF(message.conversation_key, ''), 'Message Hub')"
)
_DELIVERY_WITH_SOURCE_COLUMNS = (
    _DELIVERY_WITH_GATEWAY_COLUMNS
    + f", {_SOURCE_TYPE_SQL}, {_SOURCE_LABEL_SQL}, message.conversation_key"
)
_BULK_DELIVERY_TRANSITIONS = {
    "acknowledge": (("held",), "acknowledged"),
    "cancel": (
        ("pending", "retry_wait", "held", "dead", "uncertain"),
        "cancelled",
    ),
    "release": (("held",), "pending"),
    "retry": (("dead", "retry_wait"), "pending"),
}


class MessageHubStorage:
    """PostgreSQL persistence and leasing for the generic message queue."""

    def __init__(self) -> None:
        self._db = JobDb.instance()

    # ------------------------------------------------------------------
    # Gateways
    # ------------------------------------------------------------------

    def get_gateways(self, enabled_only: bool = False) -> list[MessageGateway]:
        where = " WHERE enabled = 1" if enabled_only else ""
        rows = self._db.execute(
            f"SELECT {_GATEWAY_COLUMNS} FROM message_gateways{where} ORDER BY name, id"
        ).fetchall()
        return [MessageGateway.from_db_row(row) for row in rows]

    def get_gateway(self, gateway_id: int) -> Optional[MessageGateway]:
        row = self._db.execute(
            f"SELECT {_GATEWAY_COLUMNS} FROM message_gateways WHERE id = %s",
            (gateway_id,),
        ).fetchone()
        return MessageGateway.from_db_row(row) if row else None

    def get_gateway_by_key(self, key: str) -> Optional[MessageGateway]:
        row = self._db.execute(
            f"SELECT {_GATEWAY_COLUMNS} FROM message_gateways WHERE key = %s",
            (key,),
        ).fetchone()
        return MessageGateway.from_db_row(row) if row else None

    def save_gateway(
        self,
        *,
        gateway_id: int,
        key: str,
        name: str,
        gateway_type: str,
        enabled: bool,
        config: dict[str, Any],
    ) -> MessageGateway:
        try:
            if gateway_id:
                row = self._db.execute(
                    "UPDATE message_gateways SET name = %s, type = %s, enabled = %s, "
                    "status = CASE WHEN %s = 1 THEN "
                    "  CASE WHEN status = 'disabled' THEN 'unknown' ELSE status END "
                    "ELSE 'disabled' END, config = %s, updated_at = NOW() "
                    "WHERE id = %s AND key = %s RETURNING " + _GATEWAY_COLUMNS,
                    (
                        name,
                        gateway_type,
                        1 if enabled else 0,
                        1 if enabled else 0,
                        json.dumps(config),
                        gateway_id,
                        key,
                    ),
                ).fetchone()
                if row is None:
                    raise KeyError("Gateway not found or key does not match")
            else:
                row = self._db.execute(
                    "INSERT INTO message_gateways (key, name, type, enabled, status, config) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING " + _GATEWAY_COLUMNS,
                    (
                        key,
                        name,
                        gateway_type,
                        1 if enabled else 0,
                        "unknown" if enabled else "disabled",
                        json.dumps(config),
                    ),
                ).fetchone()
            self._db.commit()
            return MessageGateway.from_db_row(row)
        except Exception:
            self._db.rollback()
            raise

    def set_gateway_enabled(self, key: str, enabled: bool) -> Optional[MessageGateway]:
        row = self._db.execute(
            "UPDATE message_gateways SET enabled = %s, status = %s, "
            "consecutive_failures = 0, consecutive_successes = 0, updated_at = NOW() "
            "WHERE key = %s RETURNING " + _GATEWAY_COLUMNS,
            (1 if enabled else 0, "unknown" if enabled else "disabled", key),
        ).fetchone()
        self._db.commit()
        return MessageGateway.from_db_row(row) if row else None

    def update_gateway_health(
        self,
        gateway_id: int,
        *,
        status: str,
        consecutive_failures: int,
        consecutive_successes: int,
        last_error: str | None,
        checked_at: datetime,
        healthy_at: datetime | None,
    ) -> MessageGateway:
        row = self._db.execute(
            "UPDATE message_gateways SET status = %s, consecutive_failures = %s, "
            "consecutive_successes = %s, last_error = %s, last_checked_at = %s, "
            "last_healthy_at = COALESCE(%s, last_healthy_at), updated_at = NOW() "
            "WHERE id = %s RETURNING " + _GATEWAY_COLUMNS,
            (
                status,
                consecutive_failures,
                consecutive_successes,
                last_error,
                checked_at,
                healthy_at,
                gateway_id,
            ),
        ).fetchone()
        self._db.commit()
        if row is None:
            raise KeyError(f"Gateway {gateway_id} not found")
        return MessageGateway.from_db_row(row)

    # ------------------------------------------------------------------
    # Messages and deliveries
    # ------------------------------------------------------------------

    def enqueue(
        self,
        *,
        direction: str,
        kind: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
        priority: int,
        expires_at: datetime,
        deliveries: list[dict[str, Any]],
        attachments: list[dict[str, Any]] | None = None,
        source_gateway_id: int | None = None,
        source_endpoint_id: int | None = None,
        external_id: str | None = None,
        conversation_key: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[HubMessage, list[MessageDelivery]]:
        try:
            row = self._db.execute(
                "INSERT INTO message_hub_messages "
                "(direction, kind, source_gateway_id, source_endpoint_id, external_id, "
                "conversation_key, payload, metadata, priority, idempotency_key, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING RETURNING " + _MESSAGE_COLUMNS,
                (
                    direction,
                    kind,
                    source_gateway_id,
                    source_endpoint_id,
                    external_id,
                    conversation_key,
                    json.dumps(payload),
                    json.dumps(metadata),
                    priority,
                    idempotency_key,
                    expires_at,
                ),
            ).fetchone()

            existing_message = row is None
            if existing_message:
                row = self._find_existing_message_row(
                    idempotency_key=idempotency_key,
                    source_gateway_id=source_gateway_id,
                    external_id=external_id,
                )
                if row is None:
                    raise RuntimeError("Message conflicted with an existing row but could not be resolved")

            message = HubMessage.from_db_row(row)
            self._store_attachments(
                message,
                attachments or [],
                allow_insert=not existing_message,
            )
            queued: list[MessageDelivery] = []
            for spec in deliveries:
                gateway = self.get_gateway_by_key(str(spec["gateway_key"]))
                if gateway is None:
                    raise KeyError(f"Unknown gateway: {spec['gateway_key']}")

                address = dict(spec.get("address") or {})
                delivery_payload = dict(spec.get("payload") or payload)
                recipient_key = str(spec["recipient_key"])
                recovery_policy = str(spec.get("recovery_policy", "replay"))
                initial_status = "held" if (
                    recovery_policy == "inbox_only"
                    or (recovery_policy == "digest_hold" and gateway.status == "down")
                ) else "pending"
                if recovery_policy == "latest_only":
                    self._supersede_older_latest(gateway.id, address)
                delivery_key = str(spec.get("idempotency_key") or "").strip() or self._delivery_key(
                    message.id,
                    gateway.id,
                    spec.get("target_endpoint_id"),
                    address,
                )
                delivery_row = self._db.execute(
                    "INSERT INTO message_hub_deliveries "
                    "(message_id, gateway_id, target_endpoint_id, route_id, address, payload, "
                    "recipient_key, status, recovery_policy, priority, max_attempts, idempotency_key, "
                    "dispatch_token, available_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "COALESCE(%s, NOW())) "
                    "ON CONFLICT (idempotency_key) DO UPDATE "
                    "SET idempotency_key = EXCLUDED.idempotency_key RETURNING " + _DELIVERY_COLUMNS,
                    (
                        message.id,
                        gateway.id,
                        spec.get("target_endpoint_id"),
                        spec.get("route_id"),
                        json.dumps(address),
                        json.dumps(delivery_payload),
                        recipient_key,
                        initial_status,
                        recovery_policy,
                        int(spec.get("priority", priority)),
                        int(spec.get("max_attempts", 8)),
                        delivery_key,
                        uuid.uuid4().hex,
                        spec.get("available_at"),
                    ),
                ).fetchone()
                delivery = MessageDelivery.from_db_row(delivery_row)
                self._link_acknowledgements(
                    delivery,
                    list(spec.get("acknowledge_delivery_ids") or []),
                )
                queued.append(delivery)

            self._db.commit()
            return message, queued
        except Exception:
            self._db.rollback()
            raise

    def _store_attachments(
        self,
        message: HubMessage,
        attachments: list[dict[str, Any]],
        *,
        allow_insert: bool,
    ) -> list[MessageAttachment]:
        rows = self._db.execute(
            f"SELECT {_ATTACHMENT_COLUMNS} FROM message_hub_attachments "
            "WHERE message_id = %s ORDER BY position",
            (message.id,),
        ).fetchall()
        existing = [MessageAttachment.from_db_row(row) for row in rows]
        requested_identity = [
            (
                int(item["position"]),
                str(item["content_type"]),
                item.get("filename"),
                int(item["size_bytes"]),
                str(item["sha256"]),
            )
            for item in attachments
        ]
        existing_identity = [
            (
                item.position,
                item.content_type,
                item.filename,
                item.size_bytes,
                item.sha256,
            )
            for item in existing
        ]
        if existing or not allow_insert:
            if existing_identity != requested_identity:
                raise ValueError(
                    "idempotent message was submitted with different attachments"
                )
            return existing

        stored = []
        for item in attachments:
            row = self._db.execute(
                "INSERT INTO message_hub_attachments "
                "(message_id, position, content_type, filename, content, size_bytes, sha256) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING "
                + _ATTACHMENT_COLUMNS,
                (
                    message.id,
                    item["position"],
                    item["content_type"],
                    item.get("filename"),
                    item["content"],
                    item["size_bytes"],
                    item["sha256"],
                ),
            ).fetchone()
            stored.append(MessageAttachment.from_db_row(row))
        return stored

    def _link_acknowledgements(
        self,
        response_delivery: MessageDelivery,
        held_delivery_ids: list[int],
    ) -> None:
        linked_rows = self._db.execute(
            "SELECT held_delivery_id FROM message_delivery_ack_links "
            "WHERE response_delivery_id = %s ORDER BY held_delivery_id",
            (response_delivery.id,),
        ).fetchall()
        linked_ids = {int(row[0]) for row in linked_rows}
        requested_ids = set(held_delivery_ids)

        if linked_ids:
            if linked_ids != requested_ids:
                raise ValueError(
                    "idempotent delivery was submitted with different acknowledgement IDs"
                )
            return
        if not requested_ids:
            return
        if response_delivery.status not in {"pending", "held"}:
            raise ValueError("cannot attach acknowledgements to a processed delivery")

        rows = self._db.execute(
            "SELECT held.id FROM message_hub_deliveries held "
            "WHERE held.id = ANY(%s) AND held.recipient_key = %s "
            "AND held.status = 'held' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM message_delivery_ack_links existing_link "
            "  JOIN message_hub_deliveries response "
            "    ON response.id = existing_link.response_delivery_id "
            "  WHERE existing_link.held_delivery_id = held.id "
            "  AND existing_link.response_delivery_id <> %s "
            "  AND response.status IN ('pending', 'leased', 'retry_wait', 'held', 'uncertain')"
            ") "
            "FOR UPDATE",
            (
                sorted(requested_ids),
                response_delivery.recipient_key,
                response_delivery.id,
            ),
        ).fetchall()
        eligible_ids = {int(row[0]) for row in rows}
        if eligible_ids != requested_ids:
            raise ValueError(
                "acknowledged deliveries must be held for the response recipient"
            )

        for held_delivery_id in sorted(requested_ids):
            self._db.execute(
                "INSERT INTO message_delivery_ack_links "
                "(response_delivery_id, held_delivery_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (response_delivery.id, held_delivery_id),
            )

    def _supersede_older_latest(self, gateway_id: int, address: dict[str, Any]) -> None:
        self._db.execute(
            "UPDATE message_hub_deliveries SET status = 'cancelled', "
            "last_error = 'superseded by a newer delivery', updated_at = NOW() "
            "WHERE gateway_id = %s AND address = %s AND recovery_policy = 'latest_only' "
            "AND status IN ('pending', 'retry_wait', 'held')",
            (gateway_id, json.dumps(address)),
        )

    def _find_existing_message_row(
        self,
        *,
        idempotency_key: str | None,
        source_gateway_id: int | None,
        external_id: str | None,
    ):
        if idempotency_key:
            row = self._db.execute(
                f"SELECT {_MESSAGE_COLUMNS} FROM message_hub_messages WHERE idempotency_key = %s",
                (idempotency_key,),
            ).fetchone()
            if row:
                return row
        if source_gateway_id is not None and external_id:
            return self._db.execute(
                f"SELECT {_MESSAGE_COLUMNS} FROM message_hub_messages "
                "WHERE source_gateway_id = %s AND external_id = %s",
                (source_gateway_id, external_id),
            ).fetchone()
        return None

    @staticmethod
    def _delivery_key(
        message_id: int,
        gateway_id: int,
        target_endpoint_id: int | None,
        address: dict[str, Any],
    ) -> str:
        identity = json.dumps(address, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        return f"hub:{message_id}:{gateway_id}:{target_endpoint_id or 0}:{digest}"

    def get_message(self, message_id: int) -> Optional[HubMessage]:
        row = self._db.execute(
            f"SELECT {_MESSAGE_COLUMNS} FROM message_hub_messages WHERE id = %s",
            (message_id,),
        ).fetchone()
        return HubMessage.from_db_row(row) if row else None

    def get_attachments(self, message_id: int) -> list[MessageAttachment]:
        rows = self._db.execute(
            f"SELECT {_ATTACHMENT_COLUMNS} FROM message_hub_attachments "
            "WHERE message_id = %s ORDER BY position",
            (message_id,),
        ).fetchall()
        return [MessageAttachment.from_db_row(row) for row in rows]

    def get_attachment_metadata(self, message_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT id, message_id, position, content_type, filename, "
            "size_bytes, sha256, created_at FROM message_hub_attachments "
            "WHERE message_id = %s ORDER BY position",
            (message_id,),
        ).fetchall()
        return [{
            "id": int(row[0]),
            "message_id": int(row[1]),
            "position": int(row[2]),
            "content_type": row[3],
            "filename": row[4],
            "size_bytes": int(row[5]),
            "sha256": row[6],
            "created_at": row[7].isoformat(),
        } for row in rows]

    def get_delivery(self, delivery_id: int) -> Optional[MessageDelivery]:
        row = self._db.execute(
            f"SELECT {_DELIVERY_WITH_GATEWAY_COLUMNS} "
            "FROM message_hub_deliveries delivery "
            "JOIN message_gateways gateway ON gateway.id = delivery.gateway_id "
            "WHERE delivery.id = %s",
            (delivery_id,),
        ).fetchone()
        return MessageDelivery.from_db_row(row, include_gateway=True) if row else None

    def get_delivery_attempts(self, delivery_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT id, delivery_id, attempt_number, outcome, provider_reference, "
            "error, started_at, completed_at FROM message_delivery_attempts "
            "WHERE delivery_id = %s ORDER BY attempt_number, id",
            (delivery_id,),
        ).fetchall()
        return [{
            "id": int(row[0]),
            "delivery_id": int(row[1]),
            "attempt_number": int(row[2]),
            "outcome": row[3],
            "provider_reference": row[4],
            "error": row[5],
            "started_at": row[6].isoformat(),
            "completed_at": row[7].isoformat(),
        } for row in rows]

    def list_deliveries(self, status: str | None = None, limit: int = 100) -> list[MessageDelivery]:
        params: list[Any] = []
        where = ""
        if status:
            where = " WHERE delivery.status = %s"
            params.append(status)
        params.append(max(1, min(int(limit), 500)))
        rows = self._db.execute(
            f"SELECT {_DELIVERY_WITH_GATEWAY_COLUMNS} "
            "FROM message_hub_deliveries delivery "
            "JOIN message_gateways gateway ON gateway.id = delivery.gateway_id"
            + where
            + " ORDER BY delivery.created_at DESC LIMIT %s",
            params,
        ).fetchall()
        return [MessageDelivery.from_db_row(row, include_gateway=True) for row in rows]

    @staticmethod
    def _delivery_search_conditions(
        *,
        statuses: list[str] | None = None,
        gateway_key: str | None = None,
        recipient: str | None = None,
        query: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        source_type: str | None = None,
        source_label: str | None = None,
        source_label_exact: str | None = None,
        conversation_key: str | None = None,
    ) -> tuple[list[str], list[Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if statuses:
            conditions.append("delivery.status = ANY(%s)")
            params.append(statuses)
        if gateway_key:
            conditions.append("gateway.key = %s")
            params.append(gateway_key)
        if recipient:
            conditions.append("delivery.recipient_key ILIKE %s")
            params.append(f"%{recipient}%")
        if query:
            conditions.append(
                "COALESCE(delivery.payload->>'text', delivery.payload->>'message', '') ILIKE %s"
            )
            params.append(f"%{query}%")
        if created_after:
            conditions.append("delivery.created_at >= %s")
            params.append(created_after)
        if created_before:
            conditions.append("delivery.created_at < %s")
            params.append(created_before)
        if source_type:
            conditions.append(f"{_SOURCE_TYPE_SQL} = %s")
            params.append(source_type)
        if source_label:
            conditions.append(f"{_SOURCE_LABEL_SQL} ILIKE %s")
            params.append(f"%{source_label}%")
        if source_label_exact:
            conditions.append(f"{_SOURCE_LABEL_SQL} = %s")
            params.append(source_label_exact)
        if conversation_key is not None:
            conditions.append("COALESCE(message.conversation_key, '') = %s")
            params.append(conversation_key)
        return conditions, params

    def search_deliveries(
        self,
        *,
        statuses: list[str] | None = None,
        gateway_key: str | None = None,
        recipient: str | None = None,
        query: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        source_type: str | None = None,
        source_label: str | None = None,
        source_label_exact: str | None = None,
        conversation_key: str | None = None,
        sort: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        conditions, params = self._delivery_search_conditions(
            statuses=statuses,
            gateway_key=gateway_key,
            recipient=recipient,
            query=query,
            created_after=created_after,
            created_before=created_before,
            source_type=source_type,
            source_label=source_label,
            source_label_exact=source_label_exact,
            conversation_key=conversation_key,
        )

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        safe_page = max(1, int(page))
        safe_page_size = max(1, min(int(page_size), 100))
        offset = (safe_page - 1) * safe_page_size
        sort_direction = "ASC" if sort == "asc" else "DESC"
        from_clause = (
            " FROM message_hub_deliveries delivery "
            "JOIN message_gateways gateway ON gateway.id = delivery.gateway_id "
            "JOIN message_hub_messages message ON message.id = delivery.message_id"
        )
        total = int(self._db.execute(
            "SELECT COUNT(*)" + from_clause + where,
            params,
        ).fetchone()[0])
        rows = self._db.execute(
            f"SELECT {_DELIVERY_WITH_SOURCE_COLUMNS}" + from_clause + where
            + f" ORDER BY delivery.created_at {sort_direction}, delivery.id {sort_direction} "
            "LIMIT %s OFFSET %s",
            [*params, safe_page_size, offset],
        ).fetchall()
        return {
            "items": [
                MessageDelivery.from_db_row(row, include_gateway=True) for row in rows
            ],
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }

    def search_delivery_groups(
        self,
        **filters: Any,
    ) -> dict[str, Any]:
        page = max(1, int(filters.pop("page", 1)))
        page_size = max(1, min(int(filters.pop("page_size", 25)), 100))
        sort = filters.pop("sort", "desc")
        conditions, params = self._delivery_search_conditions(**filters)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        from_clause = (
            " FROM message_hub_deliveries delivery "
            "JOIN message_gateways gateway ON gateway.id = delivery.gateway_id "
            "JOIN message_hub_messages message ON message.id = delivery.message_id"
        )
        group_by = (
            f" GROUP BY gateway.key, delivery.recipient_key, {_SOURCE_TYPE_SQL}, "
            f"{_SOURCE_LABEL_SQL}, message.conversation_key"
        )
        total = int(self._db.execute(
            "SELECT COUNT(*) FROM (SELECT 1" + from_clause + where + group_by + ") groups",
            params,
        ).fetchone()[0])
        direction = "ASC" if sort == "asc" else "DESC"
        offset = (page - 1) * page_size
        rows = self._db.execute(
            "SELECT gateway.key, delivery.recipient_key, "
            f"{_SOURCE_TYPE_SQL}, {_SOURCE_LABEL_SQL}, message.conversation_key, "
            "COUNT(*), MIN(delivery.created_at), MAX(delivery.created_at), "
            "(ARRAY_AGG(COALESCE(delivery.payload->>'text', "
            "delivery.payload->>'message', '<message>') "
            "ORDER BY delivery.created_at DESC, delivery.id DESC))[1] "
            + from_clause + where + group_by
            + f" ORDER BY MAX(delivery.created_at) {direction}, "
            f"MAX(delivery.id) {direction} LIMIT %s OFFSET %s",
            [*params, page_size, offset],
        ).fetchall()
        return {
            "items": [{
                "gateway_key": row[0],
                "recipient_key": row[1],
                "source_type": row[2],
                "source_label": row[3],
                "conversation_key": row[4],
                "count": int(row[5]),
                "oldest_at": row[6].isoformat(),
                "newest_at": row[7].isoformat(),
                "preview": row[8],
            } for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def claim_next(self, lease_token: str, lease_seconds: int = 360) -> Optional[MessageDelivery]:
        row = self._db.execute(
            "WITH candidate AS ("
            "  SELECT delivery.id FROM message_hub_deliveries delivery "
            "  JOIN message_hub_messages message ON message.id = delivery.message_id "
            "  JOIN message_gateways gateway ON gateway.id = delivery.gateway_id "
            "  WHERE delivery.status IN ('pending', 'retry_wait') "
            "    AND delivery.available_at <= NOW() "
            "    AND message.expires_at > NOW() "
            "    AND gateway.enabled = 1 AND gateway.status <> 'down' "
            "  ORDER BY delivery.priority DESC, delivery.available_at, delivery.created_at "
            "  FOR UPDATE OF delivery SKIP LOCKED LIMIT 1"
            ") "
            "UPDATE message_hub_deliveries delivery "
            "SET status = 'leased', lease_token = %s, "
            "leased_until = NOW() + (%s * INTERVAL '1 second'), "
            "attempts = attempts + 1, updated_at = NOW() "
            "FROM candidate, message_gateways gateway "
            "WHERE delivery.id = candidate.id AND gateway.id = delivery.gateway_id "
            "RETURNING " + _DELIVERY_WITH_GATEWAY_COLUMNS,
            (lease_token, max(30, lease_seconds)),
        ).fetchone()
        self._db.commit()
        return MessageDelivery.from_db_row(row, include_gateway=True) if row else None

    def mark_accepted(
        self,
        delivery: MessageDelivery,
        provider_reference: str | None = None,
    ) -> bool:
        try:
            row = self._db.execute(
                "UPDATE message_hub_deliveries SET status = 'accepted', accepted_at = NOW(), "
                "lease_token = NULL, leased_until = NULL, last_error = NULL, updated_at = NOW() "
                "WHERE id = %s AND status = 'leased' AND lease_token = %s RETURNING id",
                (delivery.id, delivery.lease_token),
            ).fetchone()
            if row is None:
                self._db.rollback()
                return False
            self._db.execute(
                "UPDATE message_hub_deliveries held SET status = 'acknowledged', "
                "acknowledged_at = NOW(), updated_at = NOW(), last_error = NULL "
                "FROM message_delivery_ack_links link "
                "WHERE link.response_delivery_id = %s "
                "AND held.id = link.held_delivery_id AND held.status = 'held'",
                (delivery.id,),
            )
            self._insert_attempt(delivery, "accepted", provider_reference, None)
            self._db.commit()
            return True
        except Exception:
            self._db.rollback()
            raise

    def mark_failed(
        self,
        delivery: MessageDelivery,
        error: str,
        retry_at: datetime,
    ) -> str:
        terminal = delivery.attempts >= delivery.max_attempts
        status = "dead" if terminal else "retry_wait"
        try:
            row = self._db.execute(
                "UPDATE message_hub_deliveries SET status = %s, available_at = %s, "
                "lease_token = NULL, leased_until = NULL, last_error = %s, updated_at = NOW() "
                "WHERE id = %s AND status = 'leased' AND lease_token = %s RETURNING id",
                (status, retry_at, error[:2000], delivery.id, delivery.lease_token),
            ).fetchone()
            if row is None:
                self._db.rollback()
                return delivery.status
            self._insert_attempt(delivery, "failed", None, error[:2000])
            self._db.commit()
            return status
        except Exception:
            self._db.rollback()
            raise

    def mark_uncertain(self, delivery: MessageDelivery, error: str) -> bool:
        """Stop automatic delivery after the gateway reports an ambiguous send."""
        try:
            row = self._db.execute(
                "UPDATE message_hub_deliveries SET status = 'uncertain', "
                "lease_token = NULL, leased_until = NULL, last_error = %s, updated_at = NOW() "
                "WHERE id = %s AND status = 'leased' AND lease_token = %s RETURNING id",
                (error[:2000], delivery.id, delivery.lease_token),
            ).fetchone()
            if row is None:
                self._db.rollback()
                return False
            self._insert_attempt(delivery, "uncertain", None, error[:2000])
            self._db.commit()
            return True
        except Exception:
            self._db.rollback()
            raise

    def _insert_attempt(
        self,
        delivery: MessageDelivery,
        outcome: str,
        provider_reference: str | None,
        error: str | None,
    ) -> None:
        self._db.execute(
            "INSERT INTO message_delivery_attempts "
            "(delivery_id, attempt_number, outcome, provider_reference, error) "
            "VALUES (%s, %s, %s, %s, %s)",
            (delivery.id, delivery.attempts, outcome, provider_reference, error),
        )

    def release_stale_leases(self) -> int:
        cursor = self._db.execute(
            "UPDATE message_hub_deliveries SET status = 'retry_wait', available_at = NOW(), "
            "lease_token = NULL, leased_until = NULL, "
            "last_error = 'delivery lease expired', updated_at = NOW() "
            "WHERE status = 'leased' AND leased_until < NOW()"
        )
        self._db.commit()
        return cursor.rowcount

    def expire_due(self) -> int:
        cursor = self._db.execute(
            "UPDATE message_hub_deliveries delivery SET status = 'expired', expired_at = NOW(), "
            "lease_token = NULL, leased_until = NULL, updated_at = NOW() "
            "FROM message_hub_messages message "
            "WHERE message.id = delivery.message_id AND message.expires_at <= NOW() "
            "AND delivery.status IN ('pending', 'retry_wait', 'held')"
        )
        self._db.commit()
        return cursor.rowcount

    def hold_for_outage(self, gateway_id: int) -> int:
        cursor = self._db.execute(
            "UPDATE message_hub_deliveries SET status = 'held', updated_at = NOW(), "
            "last_error = 'held during gateway outage' "
            "WHERE gateway_id = %s AND recovery_policy IN ('digest_hold', 'inbox_only') "
            "AND status IN ('pending', 'retry_wait')",
            (gateway_id,),
        )
        self._db.commit()
        return cursor.rowcount

    def get_unnotified_held(
        self, gateway_id: int, limit: int = 1000
    ) -> list[MessageDelivery]:
        rows = self._db.execute(
            f"SELECT {_DELIVERY_WITH_GATEWAY_COLUMNS} "
            "FROM message_hub_deliveries delivery "
            "JOIN message_gateways gateway ON gateway.id = delivery.gateway_id "
            "WHERE delivery.gateway_id = %s AND delivery.status = 'held' "
            "AND delivery.recovery_policy = 'digest_hold' "
            "AND delivery.recovery_notified_at IS NULL "
            "ORDER BY delivery.created_at LIMIT %s",
            (gateway_id, max(1, min(limit, 1000))),
        ).fetchall()
        return [MessageDelivery.from_db_row(row, include_gateway=True) for row in rows]

    def mark_recovery_notified(self, delivery_ids: list[int]) -> int:
        if not delivery_ids:
            return 0
        cursor = self._db.execute(
            "UPDATE message_hub_deliveries SET recovery_notified_at = NOW(), updated_at = NOW() "
            "WHERE id = ANY(%s) AND status = 'held'",
            (delivery_ids,),
        )
        self._db.commit()
        return cursor.rowcount

    def get_inbox_summary(self, recipient_key: str) -> dict[str, Any]:
        rows = self._db.execute(
            "SELECT COALESCE(NULLIF(message.metadata->>'source_type', ''), 'other'), "
            "COALESCE(NULLIF(message.metadata->>'source_label', ''), "
            "         NULLIF(message.conversation_key, ''), 'Message Hub'), "
            "COUNT(*) "
            "FROM message_hub_deliveries delivery "
            "JOIN message_hub_messages message ON message.id = delivery.message_id "
            "WHERE delivery.recipient_key = %s AND delivery.status = 'held' "
            "AND message.expires_at > NOW() "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM message_delivery_ack_links link "
            "  JOIN message_hub_deliveries response "
            "    ON response.id = link.response_delivery_id "
            "  WHERE link.held_delivery_id = delivery.id "
            "  AND response.status IN ('pending', 'leased', 'retry_wait', 'held', 'uncertain')"
            ") "
            "GROUP BY 1, 2 ORDER BY 1, COUNT(*) DESC",
            (recipient_key,),
        ).fetchall()
        sources = [{
            "source_type": row[0],
            "source_label": row[1],
            "count": int(row[2]),
        } for row in rows]
        return {
            "total": sum(item["count"] for item in sources),
            "sources": sources,
        }

    def prepare_inbox(
        self,
        recipient_key: str,
        *,
        source_type: str | None = None,
        source_label: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        conditions = [
            "delivery.recipient_key = %s",
            "delivery.status = 'held'",
            "message.expires_at > NOW()",
            "NOT EXISTS ("
            "SELECT 1 FROM message_delivery_ack_links link "
            "JOIN message_hub_deliveries response "
            "ON response.id = link.response_delivery_id "
            "WHERE link.held_delivery_id = delivery.id "
            "AND response.status IN ('pending', 'leased', 'retry_wait', 'held', 'uncertain')"
            ")",
        ]
        params: list[Any] = [recipient_key]
        if source_type:
            conditions.append("message.metadata->>'source_type' = %s")
            params.append(source_type)
        if source_label:
            conditions.append(
                "COALESCE(message.metadata->>'source_label', message.conversation_key, '') ILIKE %s"
            )
            params.append(f"%{source_label}%")
        params.append(max(1, min(int(limit), 10)))
        rows = self._db.execute(
            "SELECT delivery.id, message.created_at, message.metadata, "
            "delivery.payload, message.conversation_key "
            "FROM message_hub_deliveries delivery "
            "JOIN message_hub_messages message ON message.id = delivery.message_id "
            "WHERE " + " AND ".join(conditions) +
            " ORDER BY message.created_at, delivery.id LIMIT %s",
            params,
        ).fetchall()
        result = []
        for row in rows:
            metadata = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
            payload = row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}")
            result.append({
                "id": int(row[0]),
                "created_at": row[1],
                "source_type": metadata.get("source_type") or "other",
                "source_label": (
                    metadata.get("source_label") or row[4] or "Message Hub"
                ),
                "text": str(payload.get("text") or payload.get("message") or "<message>"),
            })
        return result

    def acknowledge_inbox(self, recipient_key: str, delivery_ids: list[int]) -> int:
        if not delivery_ids:
            return 0
        cursor = self._db.execute(
            "UPDATE message_hub_deliveries SET status = 'acknowledged', "
            "acknowledged_at = NOW(), updated_at = NOW(), last_error = NULL "
            "WHERE recipient_key = %s AND id = ANY(%s) AND status = 'held'",
            (recipient_key, delivery_ids),
        )
        self._db.commit()
        return cursor.rowcount

    def retry_delivery(self, delivery_id: int) -> Optional[MessageDelivery]:
        return self._reset_delivery(
            delivery_id,
            allowed_statuses=("dead", "retry_wait"),
            new_status="pending",
        )

    def retry_delivery_anyway(self, delivery_id: int) -> Optional[MessageDelivery]:
        """Force an ambiguous delivery again under a new transport identity."""
        return self._reset_delivery(
            delivery_id,
            allowed_statuses=("uncertain",),
            new_status="pending",
            rotate_dispatch_token=True,
        )

    def release_delivery(self, delivery_id: int) -> Optional[MessageDelivery]:
        return self._reset_delivery(
            delivery_id,
            allowed_statuses=("held",),
            new_status="pending",
        )

    def cancel_delivery(self, delivery_id: int) -> Optional[MessageDelivery]:
        return self._reset_delivery(
            delivery_id,
            allowed_statuses=("pending", "retry_wait", "held", "dead", "uncertain"),
            new_status="cancelled",
        )

    def bulk_update_deliveries(
        self,
        delivery_ids: list[int],
        action: str,
        *,
        actor_user_id: int | None = None,
        actor_username: str | None = None,
        scope: str = "selection",
        filter_snapshot: dict[str, Any] | None = None,
        operation_id: int | None = None,
        operation_complete: bool = True,
    ) -> dict[str, Any]:
        if action not in _BULK_DELIVERY_TRANSITIONS:
            raise ValueError(f"unsupported bulk delivery action: {action}")

        requested_ids = sorted(set(delivery_ids))
        if not requested_ids:
            operation = None
            if operation_id and operation_complete:
                self._complete_bulk_operation(operation_id)
                operation = self.get_bulk_operation(operation_id)
            return {
                "requested": 0, "updated": 0, "updated_ids": [], "skipped": [],
                "operation": operation,
            }

        allowed_statuses, new_status = _BULK_DELIVERY_TRANSITIONS[action]
        try:
            rows = self._db.execute(
                "SELECT id, status, available_at, last_error, acknowledged_at, expired_at "
                "FROM message_hub_deliveries "
                "WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                (requested_ids,),
            ).fetchall()
            statuses = {int(row[0]): row[1] for row in rows}
            prior_state = {int(row[0]): row for row in rows}
            eligible_ids = [
                delivery_id for delivery_id in requested_ids
                if statuses.get(delivery_id) in allowed_statuses
            ]

            updated_ids: list[int] = []
            if eligible_ids:
                updated_rows = self._db.execute(
                    "UPDATE message_hub_deliveries SET status = %s, "
                    "available_at = CASE WHEN %s = 'pending' THEN NOW() ELSE available_at END, "
                    "lease_token = NULL, leased_until = NULL, "
                    "acknowledged_at = CASE WHEN %s = 'acknowledged' THEN NOW() "
                    "ELSE acknowledged_at END, "
                    "expired_at = CASE WHEN %s = 'pending' THEN NULL ELSE expired_at END, "
                    "last_error = NULL, updated_at = NOW() "
                    "WHERE id = ANY(%s) RETURNING id",
                    (
                        new_status,
                        new_status,
                        new_status,
                        new_status,
                        eligible_ids,
                    ),
                ).fetchall()
                updated_ids = sorted(int(row[0]) for row in updated_rows)

            if updated_ids:
                operation_id = self._record_bulk_operation(
                    operation_id=operation_id,
                    action=action,
                    scope=scope,
                    actor_user_id=actor_user_id,
                    actor_username=actor_username,
                    filter_snapshot=filter_snapshot or {"delivery_ids": requested_ids},
                    prior_rows=[prior_state[item] for item in updated_ids],
                    complete=operation_complete,
                )
            elif operation_id and operation_complete:
                self._complete_bulk_operation(operation_id, commit=False)

            updated_id_set = set(updated_ids)
            skipped = []
            for delivery_id in requested_ids:
                if delivery_id in updated_id_set:
                    continue
                status = statuses.get(delivery_id)
                skipped.append({
                    "id": delivery_id,
                    "reason": "not_found" if status is None else "status_changed",
                    "status": status,
                })

            self._db.commit()
            return {
                "requested": len(requested_ids),
                "updated": len(updated_ids),
                "updated_ids": updated_ids,
                "skipped": skipped,
                "operation": self.get_bulk_operation(operation_id) if operation_id else None,
            }
        except Exception:
            self._db.rollback()
            raise

    def bulk_update_delivery_group(
        self,
        *,
        action: str,
        statuses: list[str],
        gateway_key: str,
        recipient_key: str,
        source_type: str,
        source_label: str,
        conversation_key: str,
        query: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        actor_user_id: int | None = None,
        actor_username: str | None = None,
    ) -> dict[str, Any]:
        if action not in _BULK_DELIVERY_TRANSITIONS:
            raise ValueError(f"unsupported bulk delivery action: {action}")
        allowed_statuses, _ = _BULK_DELIVERY_TRANSITIONS[action]
        eligible_statuses = sorted(set(statuses).intersection(allowed_statuses))
        if not eligible_statuses:
            return {
                "requested": 0, "updated": 0, "updated_ids": [], "skipped": [],
                "matching": 0, "truncated": False,
            }
        from_clause = (
            " FROM message_hub_deliveries delivery "
            "JOIN message_gateways gateway ON gateway.id = delivery.gateway_id "
            "JOIN message_hub_messages message ON message.id = delivery.message_id "
        )
        where = (
            "WHERE delivery.status = ANY(%s) AND gateway.key = %s "
            "AND delivery.recipient_key = %s "
            f"AND {_SOURCE_TYPE_SQL} = %s AND {_SOURCE_LABEL_SQL} = %s "
            "AND COALESCE(message.conversation_key, '') = %s"
        )
        params = [
            eligible_statuses, gateway_key, recipient_key, source_type,
            source_label, conversation_key,
        ]
        if query:
            where += (
                " AND COALESCE(delivery.payload->>'text', "
                "delivery.payload->>'message', '') ILIKE %s"
            )
            params.append(f"%{query}%")
        if created_after:
            where += " AND delivery.created_at >= %s"
            params.append(created_after)
        if created_before:
            where += " AND delivery.created_at < %s"
            params.append(created_before)
        try:
            matching = int(self._db.execute(
                "SELECT COUNT(*)" + from_clause + where,
                params,
            ).fetchone()[0])
            rows = self._db.execute(
                "SELECT delivery.id" + from_clause + where
                + " ORDER BY delivery.id FOR UPDATE OF delivery LIMIT 500",
                params,
            ).fetchall()
            delivery_ids = [int(row[0]) for row in rows]
            if not delivery_ids:
                self._db.commit()
                return {
                    "requested": 0, "updated": 0, "updated_ids": [], "skipped": [],
                    "matching": matching, "truncated": False,
                }
            result = self.bulk_update_deliveries(
                delivery_ids,
                action,
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                scope="group",
                filter_snapshot={
                    "statuses": statuses,
                    "gateway_key": gateway_key,
                    "recipient_key": recipient_key,
                    "source_type": source_type,
                    "source_label": source_label,
                    "conversation_key": conversation_key,
                    "query": query,
                    "created_after": created_after,
                    "created_before": created_before,
                },
            )
            result["matching"] = matching
            result["truncated"] = matching > len(delivery_ids)
            return result
        except Exception:
            self._db.rollback()
            raise

    def bulk_update_matching_deliveries(
        self,
        *,
        action: str,
        statuses: list[str],
        gateway_key: str | None = None,
        recipient: str | None = None,
        query: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        source_type: str | None = None,
        source_label: str | None = None,
        source_label_exact: str | None = None,
        conversation_key: str | None = None,
        actor_user_id: int | None = None,
        actor_username: str | None = None,
        operation_id: int | None = None,
    ) -> dict[str, Any]:
        if action not in _BULK_DELIVERY_TRANSITIONS:
            raise ValueError(f"unsupported bulk delivery action: {action}")
        allowed_statuses, _ = _BULK_DELIVERY_TRANSITIONS[action]
        eligible_statuses = sorted(set(statuses).intersection(allowed_statuses))
        if not eligible_statuses:
            return {
                "requested": 0, "updated": 0, "updated_ids": [], "skipped": [],
                "matching": 0, "remaining": 0, "truncated": False,
            }

        conditions, params = self._delivery_search_conditions(
            statuses=eligible_statuses,
            gateway_key=gateway_key,
            recipient=recipient,
            query=query,
            created_after=created_after,
            created_before=created_before,
            source_type=source_type,
            source_label=source_label,
            source_label_exact=source_label_exact,
            conversation_key=conversation_key,
        )
        where = " WHERE " + " AND ".join(conditions)
        from_clause = (
            " FROM message_hub_deliveries delivery "
            "JOIN message_gateways gateway ON gateway.id = delivery.gateway_id "
            "JOIN message_hub_messages message ON message.id = delivery.message_id"
        )
        try:
            matching = int(self._db.execute(
                "SELECT COUNT(*)" + from_clause + where,
                params,
            ).fetchone()[0])
            rows = self._db.execute(
                "SELECT delivery.id" + from_clause + where
                + " ORDER BY delivery.id FOR UPDATE OF delivery LIMIT 500",
                params,
            ).fetchall()
            delivery_ids = [int(row[0]) for row in rows]
            truncated = matching > len(delivery_ids)
            if not delivery_ids:
                if operation_id:
                    self._complete_bulk_operation(operation_id)
                else:
                    self._db.commit()
                return {
                    "requested": 0, "updated": 0, "updated_ids": [], "skipped": [],
                    "matching": matching, "remaining": matching, "truncated": False,
                    "operation": self.get_bulk_operation(operation_id) if operation_id else None,
                }
            filter_snapshot = {
                "statuses": statuses,
                "gateway_key": gateway_key,
                "recipient": recipient,
                "query": query,
                "created_after": created_after,
                "created_before": created_before,
                "source_type": source_type,
                "source_label": source_label,
                "source_label_exact": source_label_exact,
                "conversation_key": conversation_key,
            }
            result = self.bulk_update_deliveries(
                delivery_ids,
                action,
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                scope="filter",
                filter_snapshot=filter_snapshot,
                operation_id=operation_id,
                operation_complete=not truncated,
            )
            result["matching"] = matching
            result["remaining"] = max(0, matching - result["updated"])
            result["truncated"] = truncated
            return result
        except Exception:
            self._db.rollback()
            raise

    def _record_bulk_operation(
        self,
        *,
        operation_id: int | None,
        action: str,
        scope: str,
        actor_user_id: int | None,
        actor_username: str | None,
        filter_snapshot: dict[str, Any],
        prior_rows: list[tuple],
        complete: bool,
    ) -> int:
        if scope not in {"selection", "filter", "group"}:
            raise ValueError(f"unsupported bulk operation scope: {scope}")
        if operation_id:
            row = self._db.execute(
                "SELECT id, action, status FROM message_hub_bulk_operations "
                "WHERE id = %s FOR UPDATE",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Bulk operation not found")
            if row[1] != action or row[2] != "in_progress":
                raise ValueError("Bulk operation cannot accept another batch")
        else:
            operation_id = int(self._db.execute(
                "INSERT INTO message_hub_bulk_operations "
                "(action, scope, actor_user_id, actor_username, filter_snapshot, "
                "undo_expires_at) VALUES (%s, %s, %s, %s, %s, "
                "CASE WHEN %s = ANY(%s) THEN NOW() + INTERVAL '10 minutes' END) "
                "RETURNING id",
                (
                    action,
                    scope,
                    actor_user_id,
                    actor_username,
                    json.dumps(
                        filter_snapshot,
                        default=lambda value: value.isoformat(),
                    ),
                    action,
                    ["acknowledge", "cancel"],
                ),
            ).fetchone()[0])

        self._db.execute(
            "INSERT INTO message_hub_bulk_operation_items "
            "(operation_id, delivery_id, previous_status, previous_available_at, "
            "previous_last_error, previous_acknowledged_at, previous_expired_at) "
            "SELECT %s, item.delivery_id, item.previous_status, "
            "item.previous_available_at, item.previous_last_error, "
            "item.previous_acknowledged_at, item.previous_expired_at "
            "FROM UNNEST(%s::bigint[], %s::varchar[], %s::timestamptz[], "
            "%s::text[], %s::timestamptz[], %s::timestamptz[]) AS item "
            "(delivery_id, previous_status, previous_available_at, previous_last_error, "
            "previous_acknowledged_at, previous_expired_at) "
            "ON CONFLICT (operation_id, delivery_id) DO NOTHING",
            (
                operation_id,
                [int(row[0]) for row in prior_rows],
                [row[1] for row in prior_rows],
                [row[2] for row in prior_rows],
                [row[3] for row in prior_rows],
                [row[4] for row in prior_rows],
                [row[5] for row in prior_rows],
            ),
        )
        self._db.execute(
            "UPDATE message_hub_bulk_operations SET affected_count = affected_count + %s, "
            "status = CASE WHEN %s THEN 'completed' ELSE 'in_progress' END, "
            "completed_at = CASE WHEN %s THEN NOW() ELSE NULL END "
            "WHERE id = %s",
            (len(prior_rows), complete, complete, operation_id),
        )
        return operation_id

    def _complete_bulk_operation(self, operation_id: int, *, commit: bool = True) -> None:
        row = self._db.execute(
            "UPDATE message_hub_bulk_operations SET status = 'completed', "
            "completed_at = COALESCE(completed_at, NOW()) "
            "WHERE id = %s AND status = 'in_progress' RETURNING id",
            (operation_id,),
        ).fetchone()
        if row is None and self.get_bulk_operation(operation_id) is None:
            raise KeyError("Bulk operation not found")
        if commit:
            self._db.commit()

    @staticmethod
    def _bulk_operation_dict(row) -> dict[str, Any]:
        return {
            "id": int(row[0]),
            "action": row[1],
            "scope": row[2],
            "actor_user_id": int(row[3]) if row[3] is not None else None,
            "actor_username": row[4],
            "status": row[5],
            "affected_count": int(row[6]),
            "undone_count": int(row[7]),
            "filter_snapshot": row[8] or {},
            "created_at": row[9].isoformat(),
            "completed_at": row[10].isoformat() if row[10] else None,
            "undo_expires_at": row[11].isoformat() if row[11] else None,
            "undone_at": row[12].isoformat() if row[12] else None,
            "can_undo": bool(row[13]),
            "can_resume": bool(row[14]),
        }

    def get_bulk_operation(self, operation_id: int) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT id, action, scope, actor_user_id, actor_username, status, "
            "affected_count, undone_count, filter_snapshot, created_at, completed_at, "
            "undo_expires_at, undone_at, "
            "(action = ANY(%s) AND undo_expires_at > NOW() "
            "AND undone_count < affected_count) AS can_undo, "
            "(scope = 'filter' AND status = 'in_progress') AS can_resume "
            "FROM message_hub_bulk_operations WHERE id = %s",
            (["acknowledge", "cancel"], operation_id),
        ).fetchone()
        return self._bulk_operation_dict(row) if row else None

    def get_bulk_operations(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT id, action, scope, actor_user_id, actor_username, status, "
            "affected_count, undone_count, filter_snapshot, created_at, completed_at, "
            "undo_expires_at, undone_at, "
            "(action = ANY(%s) AND undo_expires_at > NOW() "
            "AND undone_count < affected_count) AS can_undo, "
            "(scope = 'filter' AND status = 'in_progress') AS can_resume "
            "FROM message_hub_bulk_operations ORDER BY created_at DESC, id DESC LIMIT %s",
            (["acknowledge", "cancel"], min(max(limit, 1), 100)),
        ).fetchall()
        return [self._bulk_operation_dict(row) for row in rows]

    def undo_bulk_operation(self, operation_id: int) -> dict[str, Any]:
        try:
            row = self._db.execute(
                "SELECT action, affected_count, undo_expires_at > NOW() "
                "FROM message_hub_bulk_operations WHERE id = %s FOR UPDATE",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Bulk operation not found")
            action, affected_count, within_window = row
            if action not in {"acknowledge", "cancel"}:
                raise ValueError("This bulk action cannot be undone")
            if not within_window:
                raise ValueError("The undo window has expired")
            resulting_status = _BULK_DELIVERY_TRANSITIONS[action][1]
            restored_rows = self._db.execute(
                "WITH restored AS ("
                "  UPDATE message_hub_deliveries delivery SET "
                "    status = item.previous_status, "
                "    available_at = item.previous_available_at, "
                "    lease_token = NULL, leased_until = NULL, "
                "    last_error = item.previous_last_error, "
                "    acknowledged_at = item.previous_acknowledged_at, "
                "    expired_at = item.previous_expired_at, updated_at = NOW() "
                "  FROM message_hub_bulk_operation_items item "
                "  WHERE item.operation_id = %s AND item.undone_at IS NULL "
                "    AND delivery.id = item.delivery_id AND delivery.status = %s "
                "  RETURNING delivery.id"
                ") UPDATE message_hub_bulk_operation_items item SET undone_at = NOW() "
                "WHERE item.operation_id = %s AND item.delivery_id IN "
                "(SELECT id FROM restored) RETURNING item.delivery_id",
                (operation_id, resulting_status, operation_id),
            ).fetchall()
            restored_ids = sorted(int(item[0]) for item in restored_rows)
            undone_count = int(self._db.execute(
                "SELECT COUNT(*) FROM message_hub_bulk_operation_items "
                "WHERE operation_id = %s AND undone_at IS NOT NULL",
                (operation_id,),
            ).fetchone()[0])
            status = "undone" if undone_count == int(affected_count) else "partially_undone"
            self._db.execute(
                "UPDATE message_hub_bulk_operations SET status = %s, undone_count = %s, "
                "undone_at = CASE WHEN %s = 'undone' THEN NOW() ELSE undone_at END "
                "WHERE id = %s",
                (status, undone_count, status, operation_id),
            )
            self._db.commit()
            return {
                "operation": self.get_bulk_operation(operation_id),
                "restored": len(restored_ids),
                "restored_ids": restored_ids,
                "skipped": int(affected_count) - undone_count,
            }
        except Exception:
            self._db.rollback()
            raise

    def resume_bulk_operation(self, operation_id: int) -> dict[str, Any]:
        operation = self.get_bulk_operation(operation_id)
        if operation is None:
            raise KeyError("Bulk operation not found")
        if not operation["can_resume"]:
            raise ValueError("Bulk operation cannot be resumed")
        snapshot = dict(operation["filter_snapshot"])
        return self.bulk_update_matching_deliveries(
            action=operation["action"],
            operation_id=operation_id,
            **snapshot,
        )

    def _reset_delivery(
        self,
        delivery_id: int,
        *,
        allowed_statuses: tuple[str, ...],
        new_status: str,
        rotate_dispatch_token: bool = False,
    ) -> Optional[MessageDelivery]:
        row = self._db.execute(
            "UPDATE message_hub_deliveries delivery SET status = %s, "
            "available_at = NOW(), lease_token = NULL, leased_until = NULL, "
            "dispatch_token = CASE WHEN %s THEN %s ELSE dispatch_token END, "
            "expired_at = CASE WHEN %s = 'pending' THEN NULL ELSE expired_at END, "
            "last_error = NULL, updated_at = NOW() "
            "FROM message_gateways gateway "
            "WHERE delivery.id = %s AND delivery.status = ANY(%s) "
            "AND gateway.id = delivery.gateway_id "
            "RETURNING " + _DELIVERY_WITH_GATEWAY_COLUMNS,
            (
                new_status,
                rotate_dispatch_token,
                uuid.uuid4().hex,
                new_status,
                delivery_id,
                list(allowed_statuses),
            ),
        ).fetchone()
        self._db.commit()
        return MessageDelivery.from_db_row(row, include_gateway=True) if row else None

    def get_queue_stats(self) -> dict[str, Any]:
        rows = self._db.execute(
            "SELECT gateway.key, gateway.name, gateway.status, delivery.status, "
            "COUNT(delivery.id), MIN(delivery.created_at) "
            "FROM message_gateways gateway "
            "LEFT JOIN message_hub_deliveries delivery ON delivery.gateway_id = gateway.id "
            "GROUP BY gateway.id, gateway.key, gateway.name, gateway.status, delivery.status "
            "ORDER BY gateway.name, delivery.status"
        ).fetchall()
        gateways: dict[str, dict[str, Any]] = {}
        for gateway_key, name, health, delivery_status, count, oldest in rows:
            item = gateways.setdefault(gateway_key, {
                "gateway_key": gateway_key,
                "name": name,
                "health": health,
                "deliveries": {},
            })
            if delivery_status:
                item["deliveries"][delivery_status] = {
                    "count": int(count),
                    "oldest_at": oldest.isoformat() if oldest else None,
                }
        incident_rows = self._db.execute(
            "SELECT incident.id, gateway.key, incident.error, incident.opened_at "
            "FROM message_gateway_incidents incident "
            "JOIN message_gateways gateway ON gateway.id = incident.gateway_id "
            "WHERE incident.status = 'open' ORDER BY incident.opened_at"
        ).fetchall()
        attachment_row = self._db.execute(
            "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) "
            "FROM message_hub_attachments"
        ).fetchone()
        return {
            "gateways": list(gateways.values()),
            "attachments": {
                "count": int(attachment_row[0]),
                "size_bytes": int(attachment_row[1]),
            },
            "open_incidents": [{
                "id": int(row[0]),
                "gateway_key": row[1],
                "error": row[2],
                "opened_at": row[3].isoformat(),
            } for row in incident_rows],
        }

    def cleanup_terminal(self, retention_days: int) -> dict[str, int]:
        """Remove old, fully terminal messages and closed gateway incidents."""
        days = max(1, int(retention_days))
        try:
            messages = self._db.execute(
                "DELETE FROM message_hub_messages message "
                "WHERE message.created_at < NOW() - (%s * INTERVAL '1 day') "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM message_hub_deliveries delivery "
                "  WHERE delivery.message_id = message.id "
                "  AND (delivery.status NOT IN "
                "    ('accepted', 'acknowledged', 'expired', 'dead', 'cancelled') "
                "    OR EXISTS ("
                "      SELECT 1 FROM message_hub_bulk_operation_items item "
                "      JOIN message_hub_bulk_operations operation "
                "        ON operation.id = item.operation_id "
                "      WHERE item.delivery_id = delivery.id AND item.undone_at IS NULL "
                "        AND operation.undo_expires_at > NOW()"
                "    )"
                "  )"
                ")",
                (days,),
            ).rowcount
            incidents = self._db.execute(
                "DELETE FROM message_gateway_incidents "
                "WHERE status = 'closed' AND closed_at < NOW() - (%s * INTERVAL '1 day')",
                (days,),
            ).rowcount
            self._db.commit()
            return {"messages": messages, "incidents": incidents}
        except Exception:
            self._db.rollback()
            raise

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    def open_incident(self, gateway_id: int, error: str | None) -> int:
        row = self._db.execute(
            "INSERT INTO message_gateway_incidents (gateway_id, error) VALUES (%s, %s) "
            "ON CONFLICT (gateway_id) WHERE status = 'open' "
            "DO UPDATE SET error = EXCLUDED.error RETURNING id",
            (gateway_id, (error or "")[:2000] or None),
        ).fetchone()
        self._db.commit()
        return int(row[0])

    def close_incident(self, gateway_id: int) -> int | None:
        row = self._db.execute(
            "UPDATE message_gateway_incidents SET status = 'closed', closed_at = NOW() "
            "WHERE gateway_id = %s AND status = 'open' RETURNING id",
            (gateway_id,),
        ).fetchone()
        self._db.commit()
        return int(row[0]) if row else None

    def mark_incident_notified(self, incident_id: int, recovery: bool = False) -> None:
        column = "recovery_notification_queued_at" if recovery else "down_notification_queued_at"
        self._db.execute(
            f"UPDATE message_gateway_incidents SET {column} = NOW() WHERE id = %s",
            (incident_id,),
        )
        self._db.commit()

    def get_unnotified_incidents(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT id, gateway_id, status, error, opened_at, closed_at "
            "FROM message_gateway_incidents "
            "WHERE (status = 'open' AND down_notification_queued_at IS NULL) "
            "OR (status = 'closed' AND recovery_notification_queued_at IS NULL) "
            "ORDER BY opened_at"
        ).fetchall()
        return [{
            "id": int(row[0]),
            "gateway_id": int(row[1]),
            "status": row[2],
            "error": row[3],
            "opened_at": row[4],
            "closed_at": row[5],
        } for row in rows]

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from src.models.orchestrator.MessageHub import (
    HubMessage,
    MessageAttachment,
    MessageDelivery,
    MessageGateway,
)
from src.services.core.message_gateway_client import (
    GatewayDeliveryUncertainError,
    MessageGatewayClient,
)

if TYPE_CHECKING:
    from src.persistence.MessageHubStorage import MessageHubStorage


log = logging.getLogger(__name__)

POLL_SECONDS = max(0.2, float(os.environ.get("MESSAGE_HUB_POLL_SECONDS", "1")))
HEALTH_INTERVAL_SECONDS = max(
    5, int(os.environ.get("MESSAGE_HUB_HEALTH_INTERVAL_SECONDS", "30"))
)
DOWN_THRESHOLD = max(1, int(os.environ.get("MESSAGE_HUB_DOWN_FAILURE_THRESHOLD", "3")))
UP_THRESHOLD = max(1, int(os.environ.get("MESSAGE_HUB_UP_SUCCESS_THRESHOLD", "2")))
DEFAULT_TTL_SECONDS = max(60, int(os.environ.get("MESSAGE_HUB_DEFAULT_TTL_SECONDS", "2592000")))
MAX_TTL_SECONDS = max(DEFAULT_TTL_SECONDS, 90 * 24 * 60 * 60)
RETENTION_DAYS = max(1, int(os.environ.get("MESSAGE_HUB_RETENTION_DAYS", "30")))
MAX_ATTACHMENT_BYTES = max(
    1024,
    int(os.environ.get("MESSAGE_HUB_MAX_ATTACHMENT_BYTES", str(5 * 1024 * 1024))),
)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif"}
LOCAL_TZ = ZoneInfo(os.environ.get("TZ", "Europe/Oslo"))


class MessageHubService:
    _instance: "MessageHubService | None" = None
    _lock = threading.Lock()

    def __init__(
        self,
        storage: "MessageHubStorage | None" = None,
        gateway_client: MessageGatewayClient | None = None,
    ) -> None:
        if storage is None:
            from src.persistence.MessageHubStorage import MessageHubStorage
            storage = MessageHubStorage()
        self._storage = storage
        self._gateway_client = gateway_client or MessageGatewayClient()

    @classmethod
    def instance(cls) -> "MessageHubService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def submit(
        self,
        *,
        direction: str,
        kind: str,
        payload: dict[str, Any],
        deliveries: list[dict[str, Any]],
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        priority: int = 50,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        source_gateway_key: str | None = None,
        source_endpoint_id: int | None = None,
        external_id: str | None = None,
        conversation_key: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[HubMessage, list[MessageDelivery]]:
        if direction not in {"inbound", "outbound", "internal"}:
            raise ValueError("direction must be inbound, outbound or internal")
        if not kind or len(kind) > 30:
            raise ValueError("kind must be between 1 and 30 characters")
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload must be a non-empty object")
        if not isinstance(deliveries, list) or not deliveries:
            raise ValueError("at least one delivery is required")
        if not 0 <= int(priority) <= 100:
            raise ValueError("priority must be between 0 and 100")

        normalized_attachments = self._normalize_attachments(
            [] if attachments is None else attachments
        )
        if kind == "mms" and len(normalized_attachments) != 1:
            raise ValueError("MMS messages require exactly one image attachment")
        if kind != "mms" and normalized_attachments:
            raise ValueError("attachments are currently supported only for MMS messages")

        ttl_seconds = min(max(int(ttl_seconds), 1), MAX_TTL_SECONDS)
        source_gateway_id = None
        if source_gateway_key:
            source_gateway = self._storage.get_gateway_by_key(source_gateway_key)
            if source_gateway is None:
                raise ValueError(f"unknown source gateway: {source_gateway_key}")
            source_gateway_id = source_gateway.id

        normalized_deliveries = [
            self._normalize_delivery(spec, int(priority)) for spec in deliveries
        ]
        for spec in normalized_deliveries:
            gateway = self._storage.get_gateway_by_key(spec["gateway_key"])
            if gateway is None:
                raise ValueError(f"unknown gateway: {spec['gateway_key']}")
            self._validate_gateway_delivery(
                gateway,
                spec,
                payload,
                kind=kind,
                has_attachments=bool(normalized_attachments),
            )
            spec["recipient_key"] = self._recipient_key(gateway, spec["address"])
        return self._storage.enqueue(
            direction=direction,
            kind=kind,
            payload=payload,
            metadata=metadata or {},
            priority=int(priority),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            deliveries=normalized_deliveries,
            attachments=normalized_attachments,
            source_gateway_id=source_gateway_id,
            source_endpoint_id=source_endpoint_id,
            external_id=(external_id or "")[:300] or None,
            conversation_key=(conversation_key or "")[:300] or None,
            idempotency_key=(idempotency_key or "")[:400] or None,
        )

    @staticmethod
    def _normalize_attachments(
        attachments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not isinstance(attachments, list):
            raise ValueError("attachments must be a list")
        normalized = []
        for position, item in enumerate(attachments):
            if not isinstance(item, dict):
                raise ValueError("each attachment must be an object")
            content = item.get("content")
            if not isinstance(content, bytes) or not content:
                raise ValueError("attachment content must be non-empty bytes")
            if len(content) > MAX_ATTACHMENT_BYTES:
                raise ValueError(
                    f"attachment exceeds {MAX_ATTACHMENT_BYTES}-byte limit"
                )
            content_type = str(item.get("content_type") or "").strip().lower()
            if content_type not in ALLOWED_IMAGE_TYPES:
                raise ValueError(f"unsupported attachment content type: {content_type}")
            filename = str(item.get("filename") or "").strip()[:255] or None
            normalized.append({
                "position": position,
                "content_type": content_type,
                "filename": filename,
                "content": content,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
        return normalized

    def submit_sms(
        self,
        *,
        phone_number: str,
        message: str,
        source_type: str,
        source_key: str | None = None,
        source_label: str | None = None,
        user_id: int | None = None,
        idempotency_key: str | None = None,
        recovery_policy: str = "digest_hold",
    ) -> tuple[HubMessage, list[MessageDelivery]]:
        phone = str(phone_number or "").strip()
        text = str(message or "").strip()
        if not phone or not text:
            raise ValueError("SMS phone number and message are required")
        available_at = self._sms_available_at(user_id)
        delivery = {
            "gateway_key": "sms-main",
            "address": {"phone": phone},
            "recovery_policy": recovery_policy,
        }
        if available_at is not None:
            delivery["available_at"] = available_at
        return self.submit(
            direction="outbound",
            kind="text",
            payload={"text": text},
            metadata={
                "source_type": source_type,
                "source_key": source_key,
                "source_label": source_label or source_type,
                "user_id": user_id,
            },
            deliveries=[delivery],
            conversation_key=phone,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _sms_available_at(user_id: int | None) -> datetime | None:
        if not user_id:
            return None
        from src.persistence.UserStorage import UserStorage

        user = UserStorage().get_user(int(user_id))
        quiet = (user.config or {}).get("sms_quiet_hours") if user else None
        if not isinstance(quiet, dict):
            return None
        try:
            start = datetime.strptime(str(quiet["start"]), "%H:%M").time()
            end = datetime.strptime(str(quiet["end"]), "%H:%M").time()
        except (KeyError, TypeError, ValueError):
            log.warning("Ignoring invalid SMS quiet hours for user %s", user_id)
            return None

        now = datetime.now(LOCAL_TZ)
        current = now.time().replace(tzinfo=None)
        if start == end:
            end_date = now.date() + timedelta(days=1)
        elif start < end:
            if not start <= current < end:
                return None
            end_date = now.date()
        else:
            if current >= start:
                end_date = now.date() + timedelta(days=1)
            elif current < end:
                end_date = now.date()
            else:
                return None
        return datetime.combine(end_date, end, tzinfo=LOCAL_TZ).astimezone(timezone.utc)

    @staticmethod
    def _normalize_delivery(spec: dict[str, Any], default_priority: int) -> dict[str, Any]:
        if not isinstance(spec, dict):
            raise ValueError("each delivery must be an object")
        gateway_key = str(spec.get("gateway_key") or "").strip().lower()
        if not gateway_key:
            raise ValueError("each delivery requires gateway_key")
        address = spec.get("address") or {}
        if not isinstance(address, dict):
            raise ValueError("delivery address must be an object")
        delivery_payload = spec.get("payload")
        if delivery_payload is not None and not isinstance(delivery_payload, dict):
            raise ValueError("delivery payload must be an object")
        policy = str(spec.get("recovery_policy") or "replay").strip().lower()
        if policy not in {"replay", "digest_hold", "inbox_only", "latest_only"}:
            raise ValueError(f"unsupported recovery policy: {policy}")
        priority = int(spec.get("priority", default_priority))
        if not 0 <= priority <= 100:
            raise ValueError("delivery priority must be between 0 and 100")
        max_attempts = int(spec.get("max_attempts", 8))
        if not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        acknowledge_ids = spec.get("acknowledge_delivery_ids", [])
        if acknowledge_ids is None:
            acknowledge_ids = []
        if not isinstance(acknowledge_ids, list):
            raise ValueError("acknowledge_delivery_ids must be a list")
        try:
            acknowledge_ids = sorted({int(item) for item in acknowledge_ids})
        except (TypeError, ValueError):
            raise ValueError("acknowledge_delivery_ids must contain integers") from None
        if any(item <= 0 for item in acknowledge_ids):
            raise ValueError("acknowledge_delivery_ids must contain positive integers")
        return {
            "gateway_key": gateway_key,
            "address": address,
            "payload": delivery_payload,
            "target_endpoint_id": spec.get("target_endpoint_id"),
            "route_id": spec.get("route_id"),
            "recovery_policy": policy,
            "priority": priority,
            "max_attempts": max_attempts,
            "idempotency_key": str(spec.get("idempotency_key") or "")[:500] or None,
            "available_at": spec.get("available_at"),
            "acknowledge_delivery_ids": acknowledge_ids,
        }

    @staticmethod
    def _validate_gateway_delivery(
        gateway: MessageGateway,
        spec: dict[str, Any],
        default_payload: dict[str, Any],
        *,
        kind: str,
        has_attachments: bool,
    ) -> None:
        address = spec["address"]
        payload = spec.get("payload") or default_payload
        if gateway.type == "sms":
            if not str(address.get("phone") or "").strip():
                raise ValueError("SMS deliveries require address.phone")
            if kind == "mms":
                if not has_attachments:
                    raise ValueError("MMS deliveries require an attachment")
            elif not str(payload.get("text") or payload.get("message") or "").strip():
                raise ValueError("SMS deliveries require payload.text")
        elif gateway.type == "telegram":
            if has_attachments:
                raise ValueError("Telegram media deliveries are not supported yet")
            if address.get("chat_id") is None and not address.get("self"):
                raise ValueError("Telegram deliveries require address.chat_id or address.self")
            if not str(payload.get("text") or payload.get("message") or "").strip():
                raise ValueError("Telegram deliveries require payload.text")
        elif gateway.type == "webhook":
            if has_attachments:
                raise ValueError("Webhook media deliveries are not supported yet")
            if not str(address.get("url") or "").strip():
                raise ValueError("Webhook deliveries require address.url")
        else:
            raise ValueError(f"unsupported gateway type: {gateway.type}")

    @staticmethod
    def _recipient_key(gateway: MessageGateway, address: dict[str, Any]) -> str:
        if gateway.type == "sms":
            return f"sms:{str(address['phone']).strip()}"
        if gateway.type == "telegram":
            value = "self" if address.get("self") else str(address["chat_id"])
            return f"telegram:{value}"
        if gateway.type == "webhook":
            digest = hashlib.sha256(str(address["url"]).encode("utf-8")).hexdigest()[:32]
            return f"webhook:{digest}"
        raise ValueError(f"unsupported gateway type: {gateway.type}")

    def process_one(self) -> bool:
        delivery = self._storage.claim_next(uuid.uuid4().hex)
        if delivery is None:
            return False

        try:
            attachments = self._storage.get_attachments(delivery.message_id)
            provider_reference = self._gateway_client.send(delivery, attachments)
            self._storage.mark_accepted(delivery, provider_reference)
            self._record_passive_result(delivery.gateway_id, True, "")
            return True
        except GatewayDeliveryUncertainError as exc:
            error = str(exc) or "gateway delivery outcome is uncertain"
            self._storage.mark_uncertain(delivery, error)
            log.error(
                "Message delivery %s through %s is uncertain; automatic retries stopped: %s",
                delivery.id,
                delivery.gateway_key,
                error,
            )
            return True
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            delay = min(15 * 60, 2 ** min(delivery.attempts, 9))
            delay += random.uniform(0, max(1, delay * 0.15))
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            status = self._storage.mark_failed(delivery, error, retry_at)
            self._record_passive_result(delivery.gateway_id, False, error)
            log.warning(
                "Message delivery %s through %s failed (%s): %s",
                delivery.id,
                delivery.gateway_key,
                status,
                error,
            )
            return True

    def get_gateways(self) -> list[MessageGateway]:
        return self._storage.get_gateways()

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
        return self._storage.save_gateway(
            gateway_id=gateway_id,
            key=key,
            name=name,
            gateway_type=gateway_type,
            enabled=enabled,
            config=config,
        )

    def set_gateway_enabled(self, key: str, enabled: bool) -> MessageGateway | None:
        return self._storage.set_gateway_enabled(key, enabled)

    def get_message(self, message_id: int) -> HubMessage | None:
        return self._storage.get_message(message_id)

    def get_attachments(self, message_id: int) -> list[MessageAttachment]:
        return self._storage.get_attachments(message_id)

    def get_attachment_metadata(self, message_id: int) -> list[dict[str, Any]]:
        return self._storage.get_attachment_metadata(message_id)

    def list_deliveries(
        self, status: str | None = None, limit: int = 100
    ) -> list[MessageDelivery]:
        return self._storage.list_deliveries(status=status, limit=limit)

    def get_inbox_summary(self, recipient_key: str) -> dict[str, Any]:
        return self._storage.get_inbox_summary(recipient_key)

    def prepare_inbox(
        self,
        recipient_key: str,
        *,
        source_type: str | None = None,
        source_label: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        items = self._storage.prepare_inbox(
            recipient_key,
            source_type=source_type,
            source_label=source_label,
            limit=limit,
        )
        if not items:
            return {"message": "No waiting messages.", "delivery_ids": []}
        lines = []
        for item in items:
            stamp = item["created_at"].astimezone(LOCAL_TZ).strftime("%d.%m %H:%M")
            body = " ".join(item["text"].replace("\n", " ").split())
            lines.append(f"{stamp} [{item['source_label']}] {body[:100]}")
        return {
            "message": "Waiting messages:\n" + "\n".join(lines),
            "delivery_ids": [item["id"] for item in items],
        }

    def acknowledge_inbox(self, recipient_key: str, delivery_ids: list[int]) -> int:
        return self._storage.acknowledge_inbox(recipient_key, delivery_ids)

    def get_queue_stats(self) -> dict[str, Any]:
        return self._storage.get_queue_stats()

    def retry_delivery(self, delivery_id: int) -> MessageDelivery | None:
        return self._storage.retry_delivery(delivery_id)

    def retry_delivery_anyway(self, delivery_id: int) -> MessageDelivery | None:
        return self._storage.retry_delivery_anyway(delivery_id)

    def release_delivery(self, delivery_id: int) -> MessageDelivery | None:
        return self._storage.release_delivery(delivery_id)

    def cancel_delivery(self, delivery_id: int) -> MessageDelivery | None:
        return self._storage.cancel_delivery(delivery_id)

    def maintain_queue(self) -> None:
        self._storage.release_stale_leases()
        self._storage.expire_due()

    def cleanup_queue(self) -> dict[str, int]:
        return self._storage.cleanup_terminal(RETENTION_DAYS)

    def monitor_gateways_once(self) -> None:
        for gateway in self._storage.get_gateways(enabled_only=True):
            result = self._gateway_client.check_ready(gateway)
            if result is None:
                continue
            healthy, error = result
            self._record_health_result(gateway, healthy, error)
        self._flush_incident_notifications()

    def _flush_incident_notifications(self) -> None:
        for incident in self._storage.get_unnotified_incidents():
            gateway = self._storage.get_gateway(incident["gateway_id"])
            if gateway is None:
                continue
            recovered = incident["status"] == "closed"
            if self._queue_gateway_alert(gateway, incident["id"], recovered=recovered):
                self._storage.mark_incident_notified(
                    incident["id"], recovery=recovered
                )

    def _record_passive_result(self, gateway_id: int, healthy: bool, error: str) -> None:
        gateway = self._storage.get_gateway(gateway_id)
        if gateway is not None:
            self._record_health_result(gateway, healthy, error)

    def _record_health_result(
        self, gateway: MessageGateway, healthy: bool, error: str
    ) -> None:
        previous_status = gateway.status
        now = datetime.now(timezone.utc)
        if healthy:
            successes = gateway.consecutive_successes + 1
            failures = 0
            if successes >= UP_THRESHOLD:
                status = "healthy"
            elif previous_status == "down":
                status = "down"
            else:
                status = "degraded"
            last_error = None
            healthy_at = now
        else:
            successes = 0
            failures = gateway.consecutive_failures + 1
            status = "down" if failures >= DOWN_THRESHOLD else "degraded"
            last_error = error[:2000] or "gateway readiness check failed"
            healthy_at = None

        updated = self._storage.update_gateway_health(
            gateway.id,
            status=status,
            consecutive_failures=failures,
            consecutive_successes=successes,
            last_error=last_error,
            checked_at=now,
            healthy_at=healthy_at,
        )
        if previous_status != "down" and updated.status == "down":
            held = self._storage.hold_for_outage(gateway.id)
            if held:
                log.info("Held %d delivery/deliveries for down gateway %s", held, gateway.key)
            incident_id = self._storage.open_incident(gateway.id, last_error)
            if self._queue_gateway_alert(updated, incident_id, recovered=False):
                self._storage.mark_incident_notified(incident_id)
        elif previous_status == "down" and updated.status == "healthy":
            incident_id = self._storage.close_incident(gateway.id)
            if incident_id:
                self._queue_recovery_digests(updated, incident_id)
                if self._queue_gateway_alert(updated, incident_id, recovered=True):
                    self._storage.mark_incident_notified(incident_id, recovery=True)

    def _queue_recovery_digests(
        self, gateway: MessageGateway, incident_id: int
    ) -> None:
        held = self._storage.get_unnotified_held(gateway.id)
        grouped: dict[str, list[MessageDelivery]] = {}
        for delivery in held:
            address_key = json.dumps(
                delivery.address, sort_keys=True, separators=(",", ":")
            )
            grouped.setdefault(address_key, []).append(delivery)

        for address_key, items in grouped.items():
            address = items[0].address
            count = len(items)
            digest = hashlib.sha256(address_key.encode("utf-8")).hexdigest()[:16]
            text = (
                f"{count} message{'s' if count != 1 else ''} were held while "
                f"{gateway.name} was unavailable. Reply inbox to retrieve them."
            )
            self.submit(
                direction="internal",
                kind="recovery_digest",
                payload={"text": text},
                deliveries=[{
                    "gateway_key": gateway.key,
                    "address": address,
                    "priority": 90,
                    "recovery_policy": "replay",
                    "idempotency_key": f"gateway-incident:{incident_id}:digest:{digest}",
                }],
                metadata={
                    "gateway_key": gateway.key,
                    "incident_id": incident_id,
                    "held_count": count,
                },
                priority=90,
                ttl_seconds=24 * 60 * 60,
                idempotency_key=f"gateway-incident:{incident_id}:digest:{digest}",
            )
            self._storage.mark_recovery_notified([item.id for item in items])

    def _queue_gateway_alert(
        self, gateway: MessageGateway, incident_id: int, recovered: bool
    ) -> bool:
        targets = self._alert_targets()
        deliveries = []
        for index, target in enumerate(targets):
            target_key = str(target.get("gateway_key") or "").strip().lower()
            if not target_key or (not recovered and target_key == gateway.key):
                continue
            target_gateway = self._storage.get_gateway_by_key(target_key)
            if target_gateway is None or not target_gateway.enabled or target_gateway.status == "down":
                continue
            deliveries.append({
                "gateway_key": target_key,
                "address": target.get("address") or {},
                "priority": 100,
                "max_attempts": 20,
                "recovery_policy": "replay",
                "idempotency_key": (
                    f"gateway-incident:{incident_id}:"
                    f"{'up' if recovered else 'down'}:{target_key}:{index}"
                ),
            })
        if not deliveries:
            return False

        if recovered:
            text = f"{gateway.name} gateway recovered and queued deliveries can resume."
        else:
            detail = f" Last error: {gateway.last_error[:180]}" if gateway.last_error else ""
            text = f"{gateway.name} gateway is down; new deliveries will remain queued.{detail}"
        self.submit(
            direction="internal",
            kind="gateway_status",
            payload={"text": text},
            deliveries=deliveries,
            metadata={"gateway_key": gateway.key, "incident_id": incident_id},
            priority=100,
            ttl_seconds=24 * 60 * 60,
            idempotency_key=f"gateway-incident:{incident_id}:{'up' if recovered else 'down'}",
        )
        return True

    @staticmethod
    def _alert_targets() -> list[dict[str, Any]]:
        raw = os.environ.get("MESSAGE_HUB_ALERT_TARGETS", "").strip()
        if raw:
            try:
                value = json.loads(raw)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            except (TypeError, ValueError):
                log.exception("MESSAGE_HUB_ALERT_TARGETS is not valid JSON")
        return []


class MessageHubRuntime:
    _instance: "MessageHubRuntime | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._started = False
        self._stop = threading.Event()

    @classmethod
    def instance(cls) -> "MessageHubRuntime":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        threading.Thread(
            target=self._delivery_loop,
            daemon=True,
            name="message-hub-delivery",
        ).start()
        threading.Thread(
            target=self._health_loop,
            daemon=True,
            name="message-hub-health",
        ).start()
        log.info("Message Hub runtime started")

    def _delivery_loop(self) -> None:
        maintenance_at = 0.0
        cleanup_at = 0.0
        while not self._stop.is_set():
            try:
                service = MessageHubService.instance()
                now = time.monotonic()
                if now >= maintenance_at:
                    service.maintain_queue()
                    maintenance_at = now + 30
                if now >= cleanup_at:
                    removed = service.cleanup_queue()
                    if any(removed.values()):
                        log.info("Message Hub retention cleanup: %s", removed)
                    cleanup_at = now + 60 * 60
                processed = service.process_one()
                if not processed:
                    self._stop.wait(POLL_SECONDS)
            except Exception:
                log.exception("Message Hub delivery loop failed")
                self._stop.wait(min(5, POLL_SECONDS * 5))
            finally:
                self._close_db_connection()

    def _health_loop(self) -> None:
        # Startup grace lets connector containers initialize first.
        while not self._stop.wait(HEALTH_INTERVAL_SECONDS):
            try:
                MessageHubService.instance().monitor_gateways_once()
            except Exception:
                log.exception("Message Hub health loop failed")
            finally:
                self._close_db_connection()

    @staticmethod
    def _close_db_connection() -> None:
        try:
            from src.persistence.JobDb import JobDb
            JobDb.instance().close_connection()
        except Exception:
            pass

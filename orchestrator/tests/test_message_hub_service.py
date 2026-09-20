import sys
import types
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


# Avoid executing src/__init__.py, which boots the Flask app and database.
src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.models.orchestrator.MessageHub import (
    HubMessage,
    MessageAttachment,
    MessageDelivery,
    MessageGateway,
)
from src.services.core.message_hub_service import MessageHubService
from src.services.core.message_gateway_client import GatewayDeliveryUncertainError


NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


def _gateway(status="healthy", failures=0, successes=2):
    return MessageGateway(
        id=1,
        key="sms-main",
        name="SMS modem",
        type="sms",
        enabled=True,
        status=status,
        config={},
        consecutive_failures=failures,
        consecutive_successes=successes,
        last_error=None,
        last_checked_at=NOW,
        last_healthy_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _delivery(attempts=1, max_attempts=3):
    return MessageDelivery(
        id=10,
        message_id=20,
        gateway_id=1,
        target_endpoint_id=None,
        route_id=None,
        address={"phone": "+4712345678"},
        payload={"text": "hello"},
        status="leased",
        recovery_policy="replay",
        priority=50,
        attempts=attempts,
        max_attempts=max_attempts,
        available_at=NOW,
        lease_token="lease",
        leased_until=NOW + timedelta(minutes=5),
        accepted_at=None,
        expired_at=None,
        recovery_notified_at=None,
        last_error=None,
        idempotency_key="delivery-10",
        dispatch_token="dispatch-10",
        created_at=NOW,
        updated_at=NOW,
        recipient_key="sms:+4712345678",
        acknowledged_at=None,
        gateway_key="sms-main",
        gateway_type="sms",
        gateway_config={},
    )


class _FakeStorage:
    def __init__(self):
        self.gateway = _gateway()
        self.claimed = None
        self.accepted = []
        self.failed = []
        self.uncertain = []
        self.enqueued = []
        self.opened = []
        self.closed = []
        self.notified = []
        self.held_for_outage = []
        self.held = []
        self.recovery_notified = []
        self.unnotified_incidents = []
        self.inbox_summary = {"total": 0, "sources": []}
        self.inbox_items = []
        self.acknowledged = []
        self.cleaned_with = []
        self.attachments = []

    def get_gateway(self, gateway_id):
        return self.gateway if gateway_id == self.gateway.id else None

    def get_gateway_by_key(self, key):
        return self.gateway if key == self.gateway.key else None

    def get_gateways(self, enabled_only=False):
        return [self.gateway]

    def update_gateway_health(self, gateway_id, **values):
        self.gateway = replace(
            self.gateway,
            status=values["status"],
            consecutive_failures=values["consecutive_failures"],
            consecutive_successes=values["consecutive_successes"],
            last_error=values["last_error"],
            last_checked_at=values["checked_at"],
            last_healthy_at=values["healthy_at"] or self.gateway.last_healthy_at,
        )
        return self.gateway

    def enqueue(self, **values):
        self.enqueued.append(values)
        message = HubMessage(
            id=20,
            direction=values["direction"],
            kind=values["kind"],
            source_gateway_id=values.get("source_gateway_id"),
            source_endpoint_id=values.get("source_endpoint_id"),
            external_id=values.get("external_id"),
            conversation_key=values.get("conversation_key"),
            payload=values["payload"],
            metadata=values["metadata"],
            priority=values["priority"],
            idempotency_key=values.get("idempotency_key"),
            created_at=NOW,
            expires_at=values["expires_at"],
        )
        return message, []

    def get_attachments(self, message_id):
        return list(self.attachments)

    def claim_next(self, lease_token):
        if self.claimed is None:
            return None
        return replace(self.claimed, lease_token=lease_token)

    def mark_accepted(self, delivery, provider_reference=None):
        self.accepted.append((delivery, provider_reference))
        self.claimed = None
        return True

    def mark_failed(self, delivery, error, retry_at):
        self.failed.append((delivery, error, retry_at))
        self.claimed = None
        return "dead" if delivery.attempts >= delivery.max_attempts else "retry_wait"

    def mark_uncertain(self, delivery, error):
        self.uncertain.append((delivery, error))
        self.claimed = None
        return True

    def open_incident(self, gateway_id, error):
        self.opened.append((gateway_id, error))
        return 100

    def close_incident(self, gateway_id):
        self.closed.append(gateway_id)
        return 100

    def mark_incident_notified(self, incident_id, recovery=False):
        self.notified.append((incident_id, recovery))

    def hold_for_outage(self, gateway_id):
        self.held_for_outage.append(gateway_id)
        return 0

    def get_unnotified_held(self, gateway_id):
        return list(self.held)

    def mark_recovery_notified(self, delivery_ids):
        self.recovery_notified.extend(delivery_ids)
        return len(delivery_ids)

    def get_unnotified_incidents(self):
        return list(self.unnotified_incidents)

    def get_inbox_summary(self, recipient_key):
        return self.inbox_summary

    def prepare_inbox(self, recipient_key, **filters):
        return list(self.inbox_items)

    def acknowledge_inbox(self, recipient_key, delivery_ids):
        self.acknowledged.append((recipient_key, delivery_ids))
        return len(delivery_ids)

    def cleanup_terminal(self, retention_days):
        self.cleaned_with.append(retention_days)
        return {"messages": 2, "incidents": 1}


class _FakeGatewayClient:
    def __init__(self):
        self.error = None
        self.uncertain_error = None
        self.probes = []

    def send(self, delivery, attachments=None):
        if self.uncertain_error:
            raise GatewayDeliveryUncertainError(self.uncertain_error)
        if self.error:
            raise RuntimeError(self.error)
        self.attachments = list(attachments or [])
        return "provider-123"

    def check_ready(self, gateway):
        if self.probes:
            return self.probes.pop(0)
        return None


class MessageHubServiceTests(unittest.TestCase):
    def setUp(self):
        self.storage = _FakeStorage()
        self.client = _FakeGatewayClient()
        self.service = MessageHubService(self.storage, self.client)

    def test_submit_normalizes_a_delivery_and_resolves_source_gateway(self):
        message, deliveries = self.service.submit(
            direction="outbound",
            kind="text",
            payload={"text": "hello"},
            deliveries=[{
                "gateway_key": "SMS-MAIN",
                "address": {"phone": "+4712345678"},
                "recovery_policy": "digest_hold",
            }],
            source_gateway_key="sms-main",
            ttl_seconds=60,
        )

        self.assertEqual(20, message.id)
        self.assertEqual([], deliveries)
        submitted = self.storage.enqueued[0]
        self.assertEqual(1, submitted["source_gateway_id"])
        self.assertEqual("sms-main", submitted["deliveries"][0]["gateway_key"])
        self.assertEqual("digest_hold", submitted["deliveries"][0]["recovery_policy"])
        self.assertEqual(
            "sms:+4712345678", submitted["deliveries"][0]["recipient_key"]
        )

    def test_submit_normalizes_acknowledgement_delivery_ids(self):
        self.service.submit(
            direction="outbound",
            kind="text",
            payload={"text": "hello"},
            deliveries=[{
                "gateway_key": "sms-main",
                "address": {"phone": "+4712345678"},
                "acknowledge_delivery_ids": [42, "41", 42],
            }],
        )

        self.assertEqual(
            [41, 42],
            self.storage.enqueued[0]["deliveries"][0]["acknowledge_delivery_ids"],
        )

    def test_submit_rejects_invalid_acknowledgement_delivery_ids(self):
        with self.assertRaisesRegex(ValueError, "must contain integers"):
            self.service.submit(
                direction="outbound",
                kind="text",
                payload={"text": "hello"},
                deliveries=[{
                    "gateway_key": "sms-main",
                    "address": {"phone": "+4712345678"},
                    "acknowledge_delivery_ids": ["not-an-id"],
                }],
            )

    def test_submit_sms_uses_the_generic_gateway_queue(self):
        quiet_end = NOW + timedelta(hours=8)
        with patch.object(self.service, "_sms_available_at", return_value=quiet_end):
            self.service.submit_sms(
                phone_number="+4712345678",
                message="hello",
                source_type="reminder",
                source_key="42",
                source_label="Reminders",
                user_id=7,
                idempotency_key="reminder:42",
            )

        submitted = self.storage.enqueued[0]
        self.assertEqual({"text": "hello"}, submitted["payload"])
        self.assertEqual("reminder", submitted["metadata"]["source_type"])
        self.assertEqual("sms-main", submitted["deliveries"][0]["gateway_key"])
        self.assertEqual("digest_hold", submitted["deliveries"][0]["recovery_policy"])
        self.assertEqual(quiet_end, submitted["deliveries"][0]["available_at"])

    def test_submit_mms_normalizes_attachment_for_storage(self):
        image = b"jpeg-image"

        self.service.submit(
            direction="outbound",
            kind="mms",
            payload={"text": "Camera"},
            attachments=[{
                "content": image,
                "content_type": "IMAGE/JPEG",
                "filename": "camera.jpg",
            }],
            deliveries=[{
                "gateway_key": "sms-main",
                "address": {"phone": "+4712345678"},
            }],
        )

        attachment = self.storage.enqueued[0]["attachments"][0]
        self.assertEqual(image, attachment["content"])
        self.assertEqual("image/jpeg", attachment["content_type"])
        self.assertEqual(len(image), attachment["size_bytes"])
        self.assertEqual(64, len(attachment["sha256"]))

    def test_submit_mms_rejects_missing_attachment(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.service.submit(
                direction="outbound",
                kind="mms",
                payload={"text": "Camera"},
                deliveries=[{
                    "gateway_key": "sms-main",
                    "address": {"phone": "+4712345678"},
                }],
            )

    def test_submit_mms_rejects_oversized_attachment(self):
        with patch(
            "src.services.core.message_hub_service.MAX_ATTACHMENT_BYTES", 4
        ):
            with self.assertRaisesRegex(ValueError, "exceeds 4-byte limit"):
                self.service.submit(
                    direction="outbound",
                    kind="mms",
                    payload={"text": "Camera"},
                    attachments=[{
                        "content": b"12345",
                        "content_type": "image/jpeg",
                    }],
                    deliveries=[{
                        "gateway_key": "sms-main",
                        "address": {"phone": "+4712345678"},
                    }],
                )

    def test_submit_mms_rejects_unsupported_attachment(self):
        with self.assertRaisesRegex(ValueError, "unsupported attachment"):
            self.service.submit(
                direction="outbound",
                kind="mms",
                payload={"text": "Camera"},
                attachments=[{
                    "content": b"file",
                    "content_type": "application/pdf",
                }],
                deliveries=[{
                    "gateway_key": "sms-main",
                    "address": {"phone": "+4712345678"},
                }],
            )

    def test_prepare_inbox_formats_items_without_acknowledging_them(self):
        self.storage.inbox_items = [{
            "id": 41,
            "created_at": datetime(2026, 9, 18, 10, 34, tzinfo=timezone.utc),
            "source_type": "telegram",
            "source_label": "Family",
            "text": "A message\nwith extra whitespace",
        }]

        result = self.service.prepare_inbox("sms:+4712345678")

        self.assertEqual([41], result["delivery_ids"])
        self.assertIn("18.09 12:34 [Family] A message with extra whitespace", result["message"])
        self.assertEqual([], self.storage.acknowledged)

    def test_acknowledge_inbox_is_scoped_to_recipient(self):
        count = self.service.acknowledge_inbox("sms:+4712345678", [41, 42])

        self.assertEqual(2, count)
        self.assertEqual(
            [("sms:+4712345678", [41, 42])], self.storage.acknowledged
        )

    def test_cleanup_queue_uses_configured_retention(self):
        with patch("src.services.core.message_hub_service.RETENTION_DAYS", 17):
            result = self.service.cleanup_queue()

        self.assertEqual({"messages": 2, "incidents": 1}, result)
        self.assertEqual([17], self.storage.cleaned_with)

    def test_successful_delivery_is_accepted_with_provider_reference(self):
        self.storage.claimed = _delivery()

        self.assertTrue(self.service.process_one())

        self.assertEqual("provider-123", self.storage.accepted[0][1])

    def test_delivery_worker_passes_stored_attachments_to_gateway(self):
        self.storage.claimed = _delivery()
        attachment = MessageAttachment(
            id=1,
            message_id=20,
            position=0,
            content_type="image/jpeg",
            filename="camera.jpg",
            content=b"jpeg",
            size_bytes=4,
            sha256="a" * 64,
            created_at=NOW,
        )
        self.storage.attachments = [attachment]

        self.assertTrue(self.service.process_one())

        self.assertEqual([attachment], self.client.attachments)
        self.assertEqual([], self.storage.failed)

    def test_failed_delivery_is_scheduled_for_retry(self):
        self.storage.claimed = _delivery(attempts=1, max_attempts=3)
        self.client.error = "modem offline"

        with patch("src.services.core.message_hub_service.random.uniform", return_value=0):
            self.assertTrue(self.service.process_one())

        self.assertEqual([], self.storage.accepted)
        self.assertEqual("modem offline", self.storage.failed[0][1])
        self.assertGreater(self.storage.failed[0][2], datetime.now(timezone.utc))

    def test_uncertain_delivery_stops_without_a_gateway_outage(self):
        self.storage.claimed = _delivery()
        self.client.uncertain_error = "modem acknowledgement was lost"

        self.assertTrue(self.service.process_one())

        self.assertEqual([], self.storage.failed)
        self.assertEqual(
            "modem acknowledgement was lost", self.storage.uncertain[0][1]
        )
        self.assertEqual([], self.storage.opened)

    def test_gateway_opens_one_incident_after_failure_threshold(self):
        self.storage.gateway = _gateway(status="healthy", failures=0, successes=10)
        self.client.probes = [(False, "offline")] * 4

        with patch.dict("os.environ", {"MESSAGE_HUB_ALERT_TARGETS": "[]"}, clear=False):
            for _ in range(4):
                self.service.monitor_gateways_once()

        self.assertEqual("down", self.storage.gateway.status)
        self.assertEqual([(1, "offline")], self.storage.opened)

    def test_gateway_recovery_requires_success_threshold(self):
        self.storage.gateway = _gateway(status="down", failures=3, successes=0)
        self.client.probes = [(True, ""), (True, "")]

        self.service.monitor_gateways_once()
        self.assertEqual("down", self.storage.gateway.status)
        self.service.monitor_gateways_once()

        self.assertEqual("healthy", self.storage.gateway.status)
        self.assertEqual([1], self.storage.closed)

    def test_gateway_recovery_queues_one_digest_per_held_address(self):
        self.storage.gateway = _gateway(status="down", failures=3, successes=0)
        held_one = replace(
            _delivery(), id=11, status="held", recovery_policy="digest_hold"
        )
        held_two = replace(
            _delivery(), id=12, status="held", recovery_policy="digest_hold"
        )
        self.storage.held = [held_one, held_two]
        self.client.probes = [(True, ""), (True, "")]

        self.service.monitor_gateways_once()
        self.service.monitor_gateways_once()

        digests = [item for item in self.storage.enqueued if item["kind"] == "recovery_digest"]
        self.assertEqual(1, len(digests))
        self.assertIn("2 messages", digests[0]["payload"]["text"])
        self.assertEqual([11, 12], self.storage.recovery_notified)


class MessageHubModelTests(unittest.TestCase):
    def test_delivery_db_row_with_gateway_context_is_decoded(self):
        row = (
            10, 20, 1, None, None,
            '{"phone":"+4712345678"}', '{"text":"hello"}',
            "pending", "replay", 50, 0, 8, NOW,
            None, None, None, None, None, None, "delivery-10", "dispatch-10", NOW, NOW,
            "sms:+4712345678", None,
            "sms-main", "sms", '{"base_url":"http://sms"}',
        )

        delivery = MessageDelivery.from_db_row(row, include_gateway=True)

        self.assertEqual("+4712345678", delivery.address["phone"])
        self.assertEqual("sms-main", delivery.gateway_key)
        self.assertEqual("http://sms", delivery.gateway_config["base_url"])


if __name__ == "__main__":
    unittest.main()

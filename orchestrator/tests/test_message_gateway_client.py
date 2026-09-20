import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.models.orchestrator.MessageHub import MessageAttachment, MessageDelivery
from src.services.core.message_gateway_client import (
    GatewayDeliveryUncertainError,
    MessageGatewayClient,
)


NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def _delivery():
    return MessageDelivery(
        id=10,
        message_id=20,
        gateway_id=1,
        target_endpoint_id=None,
        route_id=None,
        address={"phone": "+4712345678"},
        payload={"text": "Weather forecast"},
        status="leased",
        recovery_policy="replay",
        priority=80,
        attempts=1,
        max_attempts=8,
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
        gateway_config={"base_url": "http://sms-hub:5050"},
    )


class _Response:
    content = b'{"ok": true}'
    status_code = 200

    @staticmethod
    def raise_for_status():
        return None

    @staticmethod
    def json():
        return {"ok": True}


class _UncertainResponse(_Response):
    content = b'{"delivery_state":"uncertain"}'
    status_code = 409

    @staticmethod
    def json():
        return {
            "delivery_state": "uncertain",
            "error": "modem result is ambiguous",
        }


class MessageGatewayClientTests(unittest.TestCase):
    @patch("src.services.core.message_gateway_client.requests.post", return_value=_Response())
    def test_sms_attachment_uses_mms_endpoint(self, post):
        attachment = MessageAttachment(
            id=1,
            message_id=20,
            position=0,
            content_type="image/png",
            filename="weather.png",
            content=b"png-data",
            size_bytes=8,
            sha256="a" * 64,
            created_at=NOW,
        )

        MessageGatewayClient().send(_delivery(), [attachment])

        self.assertEqual(
            "http://sms-hub:5050/api/sms/mms/send", post.call_args.args[0]
        )
        body = post.call_args.kwargs["json"]
        self.assertEqual("Weather forecast", body["message"])
        self.assertEqual("image/png", body["media_mime_type"])
        self.assertEqual("dispatch-10", body["delivery_token"])
        self.assertEqual("cG5nLWRhdGE=", body["media_data"])

    @patch("src.services.core.message_gateway_client.requests.post", return_value=_Response())
    def test_sms_without_attachment_uses_text_endpoint(self, post):
        MessageGatewayClient().send(_delivery(), [])

        self.assertEqual("http://sms-hub:5050/api/sms/send", post.call_args.args[0])
        self.assertEqual("dispatch-10", post.call_args.kwargs["json"]["delivery_token"])

    @patch(
        "src.services.core.message_gateway_client.requests.post",
        return_value=_UncertainResponse(),
    )
    def test_sms_uncertain_response_has_a_distinct_error(self, _post):
        with self.assertRaisesRegex(
            GatewayDeliveryUncertainError, "ambiguous"
        ):
            MessageGatewayClient().send(_delivery(), [])


if __name__ == "__main__":
    unittest.main()

import asyncio
import importlib
import unittest
from pathlib import Path


# Another relay test replaces this module while isolating the TDLib wrapper.
# Load the real file under a private name so discovery order does not affect us.
module_path = Path(__file__).resolve().parents[1] / "app" / "destinations" / "sms.py"
spec = importlib.util.spec_from_file_location("sms_destination_under_test", module_path)
sms_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(sms_module)
SmsAdapter = sms_module.SmsAdapter


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message_id": 42}


class _Client:
    def __init__(self):
        self.calls = []
        self.is_closed = False

    async def post(self, url, json, headers):
        self.calls.append((url, json, headers))
        return _Response()


class SmsDestinationTests(unittest.TestCase):
    def test_submits_a_durable_sms_delivery(self):
        adapter = SmsAdapter("17", {
            "phone": "+4712345678",
            "recovery_policy": "digest_hold",
        })
        client = _Client()
        adapter._client = client
        payload = {
            "chat_id": -1001,
            "message_id": 99,
            "chat_type": "group",
            "chat_title": "Family",
            "sender_name": "Alice",
            "text": "Hello",
        }

        asyncio.run(adapter.send(payload))

        url, body, _ = client.calls[0]
        self.assertTrue(url.endswith("/api/message-hub/messages"))
        self.assertEqual("telegram-main", body["source_gateway_key"])
        self.assertEqual("-1001:99", body["external_id"])
        self.assertEqual("digest_hold", body["deliveries"][0]["recovery_policy"])
        self.assertEqual(17, body["deliveries"][0]["target_endpoint_id"])
        self.assertEqual("Family | Alice: Hello", body["payload"]["text"])

if __name__ == "__main__":
    unittest.main()

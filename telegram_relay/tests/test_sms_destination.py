import asyncio
import base64
import importlib
import sys
import types
import unittest
from pathlib import Path


destinations_package = types.ModuleType("app.destinations")
destinations_package.__path__ = [str(Path(__file__).resolve().parents[1] / "app" / "destinations")]
sys.modules.setdefault("app.destinations", destinations_package)
base_module = types.ModuleType("app.destinations.base")
base_module.AbstractDestination = object
sys.modules.setdefault("app.destinations.base", base_module)


# Another relay test replaces this module while isolating the TDLib wrapper.
# Load the real file under a private name so discovery order does not affect us.
module_path = Path(__file__).resolve().parents[1] / "app" / "destinations" / "sms.py"
spec = importlib.util.spec_from_file_location("sms_destination_under_test", module_path)
sms_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(sms_module)
SmsAdapter = sms_module.SmsAdapter


class _Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class _Client:
    def __init__(self):
        self.calls = []
        self.is_closed = False

    async def post(self, url, json, headers):
        self.calls.append((url, json, headers))
        if url.endswith("/api/sms-routing/external-messages"):
            alias = json["alias"]
            author = f"{json['author']}: " if json.get("author") else ""
            return _Response({
                "reference": 184,
                "alias": alias,
                "text": f"({alias} #184)\n{author}{json['body']}",
            })
        return _Response({"message_id": 42})


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

        registration_url, registration, _ = client.calls[0]
        self.assertTrue(registration_url.endswith("/api/sms-routing/external-messages"))
        self.assertEqual("tg/family", registration["alias"])
        url, body, _ = client.calls[1]
        self.assertTrue(url.endswith("/api/message-hub/messages"))
        self.assertEqual("telegram-main", body["source_gateway_key"])
        self.assertEqual("telegram-main:-1001:99", body["external_id"])
        self.assertEqual("digest_hold", body["deliveries"][0]["recovery_policy"])
        self.assertEqual(17, body["deliveries"][0]["target_endpoint_id"])
        self.assertEqual("(tg/family #184)\nAlice: Hello", body["payload"]["text"])
        self.assertEqual(184, body["metadata"]["sms_reference"])

    def test_submits_telegram_photo_as_mms_attachment(self):
        adapter = SmsAdapter("17", {"phone": "+4712345678"})
        client = _Client()
        adapter._client = client
        image = b"\xff\xd8\xfftelegram-photo"
        payload = {
            "chat_id": 123,
            "message_id": 99,
            "chat_type": "private",
            "sender_name": "Alice",
            "media_type": "photo",
            "caption": "Cabin",
            "media_data": image,
            "media_mime_type": "image/jpeg",
        }

        asyncio.run(adapter.send(payload))

        _, body, _ = client.calls[1]
        self.assertEqual("mms", body["kind"])
        self.assertEqual("(tg/alice #184)\nCabin", body["payload"]["text"])
        self.assertEqual("image/jpeg", body["attachments"][0]["content_type"])
        self.assertEqual("telegram-99.jpg", body["attachments"][0]["filename"])
        self.assertEqual(image, base64.b64decode(body["attachments"][0]["data_base64"]))

    def test_explicit_alias_mapping_uses_stable_chat_id(self):
        adapter = SmsAdapter("17", {
            "phone": "+4712345678",
            "conversation_aliases": {"-1001": "tg/close-family"},
        })
        self.assertEqual("tg/close-family", adapter._alias_for({
            "chat_id": -1001, "chat_title": "A renamed group",
        }))

if __name__ == "__main__":
    unittest.main()

import asyncio
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

# The production image provides python-telegram. Unit tests only need the
# forwarder's protocol construction, so supply a minimal import stub when the
# native wrapper is not installed locally.
try:
    from telegram.client import Telegram  # noqa: F401
except ImportError:
    telegram_module = types.ModuleType("telegram")
    client_module = types.ModuleType("telegram.client")
    client_module.Telegram = object
    telegram_module.client = client_module
    sys.modules["telegram"] = telegram_module
    sys.modules["telegram.client"] = client_module


def _stub_module(name, **members):
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    sys.modules[name] = module


class _Placeholder:
    pass


_stub_module("app.config", TelegramConfig=_Placeholder)
_stub_module("app.destinations.base", AbstractDestination=_Placeholder)
_stub_module("app.destinations.sms", SmsAdapter=type("SmsAdapter", (), {}))
_stub_module("app.redactor", Redactor=_Placeholder)
_stub_module("app.rules.engine", RuleEngine=_Placeholder)
_stub_module(
    "app.rules.models",
    ForwardAction=type("ForwardAction", (), {}),
    LogAction=type("LogAction", (), {}),
    SkipAction=type("SkipAction", (), {}),
    Rule=_Placeholder,
)

from app.forwarder import TelegramForwarder
from app.normalizer import NormalizedMessage


class _Result:
    error = False
    error_info = ""
    update = {"id": 123}

    def wait(self):
        return None


class _Client:
    def __init__(self):
        self.calls = []

    def call_method(self, method, params=None):
        self.calls.append((method, params))
        return _Result()


class _BotUserClient:
    def call_method(self, method, params=None):
        result = _Result()
        if method == "getUser":
            result.update = {
                "first_name": "Solar",
                "last_name": "Bot",
                "type": {"@type": "userTypeBot"},
            }
        return result


class ForwarderMediaTests(unittest.TestCase):
    def test_text_send_returns_tdlib_message_id(self):
        forwarder = TelegramForwarder.__new__(TelegramForwarder)
        forwarder._client = _Client()

        message_id = forwarder.send_message(42, "Hello")

        self.assertEqual(123, message_id)

    def test_enrichment_marks_bot_senders(self):
        forwarder = TelegramForwarder.__new__(TelegramForwarder)
        forwarder._client = _BotUserClient()
        message = NormalizedMessage(
            message_id=1,
            chat_id=-42,
            chat_title="Power chat",
            chat_type="group",
            sender_id=7,
            sender_name=None,
            text="Solar data",
            media_type=None,
            media_file_id=None,
            caption=None,
            timestamp=123,
        )

        enriched = forwarder._enrich_message(message)

        self.assertEqual("Solar Bot", enriched.sender_name)
        self.assertTrue(enriched.sender_is_bot)

    def test_reply_context_is_persisted_and_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "reply-context.json")
            forwarder = TelegramForwarder.__new__(TelegramForwarder)
            forwarder._lock = threading.Lock()
            forwarder._reply_context = {}
            forwarder._reply_context_path = path

            forwarder.set_reply_context("+4712345678", 42)

            with open(path, encoding="utf-8") as saved:
                self.assertEqual({"+4712345678": 42}, json.load(saved))
            loaded = TelegramForwarder.__new__(TelegramForwarder)
            loaded._reply_context = {}
            loaded._reply_context_path = path
            loaded._load_reply_context()
            self.assertEqual({"+4712345678": 42}, loaded._reply_context)

    def test_photo_is_staged_and_sent_as_input_message_photo(self):
        with tempfile.TemporaryDirectory() as directory:
            forwarder = TelegramForwarder.__new__(TelegramForwarder)
            forwarder._client = _Client()
            outgoing = os.path.join(directory, "outgoing")

            with patch("app.forwarder.os.path.abspath", return_value=outgoing):
                forwarder.send_photo(42, b"\xff\xd8\xffimage", "image/jpeg", "Cabin")

            method, params = forwarder._client.calls[0]
            self.assertEqual("sendMessage", method)
            content = params["input_message_content"]
            self.assertEqual("inputMessagePhoto", content["@type"])
            self.assertEqual("Cabin", content["caption"]["text"])
            self.assertTrue(os.path.exists(content["photo"]["path"]))

    def test_incoming_photo_is_downloaded_for_sms_destination(self):
        sms_class = sys.modules["app.destinations.sms"].SmsAdapter
        action_class = sys.modules["app.rules.models"].ForwardAction
        destination = sms_class()
        destination.phone = "+4712345678"
        destination.payload = None

        async def send(payload):
            destination.payload = payload

        destination.send = send
        action = action_class()
        action.destination = "sms"
        action.redact = []
        action.include_fields = None
        action.exclude_fields = None
        message = NormalizedMessage(
            message_id=99,
            chat_id=42,
            chat_title="Alice",
            chat_type="private",
            sender_id=7,
            sender_name="Alice",
            text=None,
            media_type="photo",
            media_file_id=1234,
            caption="Cabin",
            timestamp=123,
        )
        forwarder = TelegramForwarder.__new__(TelegramForwarder)
        forwarder._redactor = type(
            "IdentityRedactor",
            (),
            {"apply": staticmethod(lambda msg, _patterns: msg)},
        )()
        forwarder._download_media = Mock(return_value=(b"jpeg-data", "image/jpeg"))
        forwarder.set_reply_context = Mock()

        asyncio.run(forwarder._dispatch(action, message, "photos", {"sms": destination}))

        forwarder._download_media.assert_called_once_with(1234, "photo")
        self.assertEqual(b"jpeg-data", destination.payload["media_data"])
        self.assertEqual("image/jpeg", destination.payload["media_mime_type"])


if __name__ == "__main__":
    unittest.main()

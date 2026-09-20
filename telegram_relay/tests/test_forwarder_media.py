import json
import os
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

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


class _NormalizedMessage:
    pass


_stub_module("app.config", TelegramConfig=_Placeholder)
_stub_module("app.destinations.base", AbstractDestination=_Placeholder)
_stub_module("app.destinations.sms", SmsAdapter=type("SmsAdapter", (), {}))
_stub_module("app.normalizer", MessageNormalizer=_Placeholder, NormalizedMessage=_NormalizedMessage)
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


class ForwarderMediaTests(unittest.TestCase):
    def test_text_send_returns_tdlib_message_id(self):
        forwarder = TelegramForwarder.__new__(TelegramForwarder)
        forwarder._client = _Client()

        message_id = forwarder.send_message(42, "Hello")

        self.assertEqual(123, message_id)

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


if __name__ == "__main__":
    unittest.main()

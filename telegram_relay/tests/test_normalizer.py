import importlib.util
from pathlib import Path
import unittest


_SPEC = importlib.util.spec_from_file_location(
    "normalizer_under_test",
    Path(__file__).resolve().parents[1] / "app" / "normalizer.py",
)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
MessageNormalizer = _MODULE.MessageNormalizer


class MessageNormalizerTests(unittest.TestCase):
    def test_outgoing_message_is_ignored(self):
        update = {
            "message": {
                "id": 1,
                "chat_id": -42,
                "is_outgoing": True,
                "content": {
                    "@type": "messageText",
                    "text": {"text": "solar"},
                },
            }
        }

        self.assertIsNone(MessageNormalizer().normalize(update))

    def test_sender_bot_flag_is_included_in_payload(self):
        update = {
            "message": {
                "id": 1,
                "chat_id": -42,
                "date": 123,
                "sender_id": {"@type": "messageSenderUser", "user_id": 7},
                "content": {
                    "@type": "messageText",
                    "text": {"text": "solar"},
                },
            }
        }

        message = MessageNormalizer().normalize(update)

        self.assertIsNotNone(message)
        self.assertIsNone(message.sender_is_bot)
        self.assertIn("sender_is_bot", message.to_payload())


if __name__ == "__main__":
    unittest.main()

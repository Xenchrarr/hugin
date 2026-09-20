import unittest
from unittest.mock import MagicMock, patch

from src.command_processor import CommandProcessor


class MediaRoutingTests(unittest.TestCase):
    def setUp(self):
        self.processor = CommandProcessor.__new__(CommandProcessor)

    @patch("src.command_processor._orchestrator.lookup_user", return_value={"id": 1})
    @patch("src.api.telegram_relay.TelegramRelayClient")
    def test_uses_sticky_target_for_uncaptioned_photo(self, relay_class, _lookup):
        relay = MagicMock()
        relay.get_context.return_value = {"chat_id": 42, "title": "Family"}
        relay.send_media.return_value = True
        relay_class.return_value = relay

        result = self.processor.process_media("", "+4712345678", b"jpg", "image/jpeg")

        self.assertTrue(result.handled)
        self.assertEqual("OK photo sent to Family", result.response)
        relay.send_media.assert_called_once_with(42, b"jpg", "image/jpeg", "")

    @patch("src.command_processor._orchestrator.lookup_user", return_value={"id": 1})
    @patch("src.commands.tg.send._relay.get_conversations")
    @patch("src.api.telegram_relay.TelegramRelayClient")
    def test_explicit_target_is_selected_and_command_removed_from_caption(
        self, relay_class, get_conversations, _lookup
    ):
        get_conversations.return_value = [{"chat_id": 99, "title": "Cabin", "index": 1}]
        relay = MagicMock()
        relay.send_media.return_value = True
        relay_class.return_value = relay

        result = self.processor.process_media(
            "tg/send 1 Snow today", "+4712345678", b"jpg", "image/jpeg"
        )

        self.assertTrue(result.handled)
        relay.set_context.assert_called_once_with("+4712345678", 99)
        relay.send_media.assert_called_once_with(99, b"jpg", "image/jpeg", "Snow today")

    @patch("src.command_processor._orchestrator.lookup_user", return_value={"id": 1})
    @patch("src.api.telegram_relay.TelegramRelayClient")
    def test_photo_without_target_returns_actionable_message(self, relay_class, _lookup):
        relay = MagicMock()
        relay.get_context.return_value = None
        relay_class.return_value = relay

        result = self.processor.process_media("Cabin", "+4712345678", b"jpg", "image/jpeg")

        self.assertTrue(result.handled)
        self.assertIn("tg/use", result.response)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from src.commands.tg.use import TgUseCommand
from src.models.parsed_command import ParsedCommand


class TgUseCommandTests(unittest.TestCase):
    def _command(self, *args):
        return ParsedCommand(path="tg/use", positional=list(args), sender_phone="+4712345678")

    @patch("src.commands.tg.use._relay.set_context", return_value=True)
    @patch("src.commands.tg.send._relay.get_conversations")
    def test_selects_and_persists_numbered_conversation(self, get_conversations, set_context):
        get_conversations.return_value = [
            {"chat_id": 42, "title": "Family", "index": 1},
        ]

        result = TgUseCommand().execute(self._command("1"))

        self.assertEqual("Using: Family", result)
        set_context.assert_called_once_with("+4712345678", 42)

    def test_requires_a_target(self):
        result = TgUseCommand().execute(self._command())
        self.assertIn("ERR_BAD_ARG", result)


if __name__ == "__main__":
    unittest.main()

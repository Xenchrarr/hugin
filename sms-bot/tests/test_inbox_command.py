import unittest

from src.commands import inbox_command
from src.models.command_response import CommandResponse
from src.models.parsed_command import ParsedCommand


class _FakeOrchestrator:
    def get_message_hub_inbox_summary(self, phone):
        return {
            "total": 4,
            "sources": [
                {"source_type": "telegram", "source_label": "Family", "count": 3},
                {"source_type": "system", "source_label": "System", "count": 1},
            ],
        }

    def prepare_message_hub_inbox(self, phone, source_type=None, source_label=None, limit=5):
        return {
            "message": f"prepared:{source_type}:{source_label}",
            "delivery_ids": [11, 12],
        }


class InboxCommandTests(unittest.TestCase):
    def setUp(self):
        self.original = inbox_command._orchestrator
        inbox_command._orchestrator = _FakeOrchestrator()
        self.command = inbox_command.InboxCommand()

    def tearDown(self):
        inbox_command._orchestrator = self.original

    @staticmethod
    def _command(*args):
        return ParsedCommand(path="inbox", positional=list(args), sender_phone="+4712345678")

    def test_summary_groups_counts_by_type(self):
        result = self.command.execute(self._command())
        self.assertIn("telegram 3", result)
        self.assertIn("system 1", result)

    def test_telegram_group_filter_returns_acknowledgeable_response(self):
        result = self.command.execute(self._command("telegram", "Family"))
        self.assertIsInstance(result, CommandResponse)
        self.assertIn("prepared:telegram:Family", result.text)
        self.assertEqual([11, 12], result.ack_hub_delivery_ids)

    def test_message_hub_items_are_returned(self):
        inbox_command._orchestrator.prepare_message_hub_inbox = lambda **kwargs: {
            "message": "held hub messages",
            "delivery_ids": [21, 22],
        }

        result = self.command.execute(self._command("telegram"))

        self.assertIn("held hub messages", result.text)
        self.assertEqual([21, 22], result.ack_hub_delivery_ids)


if __name__ == "__main__":
    unittest.main()

import unittest

from src.commands.tg import list as tg_list
from src.models.parsed_command import ParsedCommand


class _FakeRelay:
    def __init__(self, conversations):
        self._conversations = conversations

    def get_conversations(self):
        return self._conversations


class TgListCommandTests(unittest.TestCase):
    def setUp(self):
        self.original_relay = tg_list._relay

    def tearDown(self):
        tg_list._relay = self.original_relay

    def test_ten_conversations_fit_in_one_gsm7_sms(self):
        tg_list._relay = _FakeRelay([
            {
                "index": index,
                "chat_id": index,
                "title": "A very long Telegram conversation title",
            }
            for index in range(1, 11)
        ])

        result = tg_list.TgListCommand().execute(ParsedCommand(path="tg/list"))

        self.assertLessEqual(len(result), 159)
        self.assertEqual(10, len(result.splitlines()))
        self.assertEqual("1. A very lon>", result.splitlines()[0])
        self.assertEqual("10. A very lon>", result.splitlines()[-1])

    def test_short_titles_are_not_padded(self):
        tg_list._relay = _FakeRelay([
            {"index": 1, "chat_id": 123, "title": "Family"},
            {"index": 2, "chat_id": 456, "title": "Work"},
        ])

        result = tg_list.TgListCommand().execute(ParsedCommand(path="tg/list"))

        self.assertEqual("1. Family\n2. Work", result)


if __name__ == "__main__":
    unittest.main()

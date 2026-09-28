import unittest

from src.commands.fb import reply as fb_reply
from src.commands.fb import send as fb_send
from src.models.parsed_command import ParsedCommand


class _FakeRelay:
    def __init__(self):
        self.sent = []

    def get_conversations(self):
        return [{"index": 1, "thread_id": "42", "title": "Alice"}]

    def send_message(self, thread_id, text):
        self.sent.append((thread_id, text))
        return True

    def set_context(self, phone, thread_id):
        return True

    def get_context(self, phone):
        return {"thread_id": "42", "title": "Alice"}


class FacebookCommandTests(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeRelay()
        self.old_send = fb_send._relay
        self.old_reply = fb_reply._relay
        fb_send._relay = self.fake
        fb_reply._relay = self.fake

    def tearDown(self):
        fb_send._relay = self.old_send
        fb_reply._relay = self.old_reply

    def test_send_resolves_conversation_number(self):
        result = fb_send.FbSendCommand().execute(
            ParsedCommand(
                path="fb/send", positional=["1", "hello"], sender_phone="+47123"
            )
        )
        self.assertEqual("Sent: Alice", result)
        self.assertEqual([("42", "hello")], self.fake.sent)

    def test_reply_uses_phone_context(self):
        result = fb_reply.FbReplyCommand().execute(
            ParsedCommand(
                path="fb/reply", positional=["hello", "again"], sender_phone="+47123"
            )
        )
        self.assertEqual("OK sent to Alice", result)
        self.assertEqual([("42", "hello again")], self.fake.sent)


if __name__ == "__main__":
    unittest.main()

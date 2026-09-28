import unittest

from src.commands.rns import list as rns_list
from src.commands.rns import reply as rns_reply
from src.commands.rns import send as rns_send
from src.commands.rns import use as rns_use
from src.models.parsed_command import ParsedCommand


class _FakeRelay:
    def __init__(self):
        self.destination = "ab" * 16
        self.sent = []
        self.contexts = []

    def get_conversations(self):
        return [{
            "index": 1,
            "destination_hash": self.destination,
            "display_name": "Alice",
        }]

    def send_message(self, destination_hash, text):
        self.sent.append((destination_hash, text))
        return True

    def set_context(self, phone, destination_hash):
        self.contexts.append((phone, destination_hash))
        return True

    def get_context(self, phone):
        return {"destination_hash": self.destination, "display_name": "Alice"}


class ReticulumCommandTests(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeRelay()
        self.previous = {
            rns_list: rns_list._relay,
            rns_send: rns_send._relay,
            rns_reply: rns_reply._relay,
            rns_use: rns_use._relay,
        }
        for module in self.previous:
            module._relay = self.fake

    def tearDown(self):
        for module, relay in self.previous.items():
            module._relay = relay

    def test_list_and_send_by_index(self):
        listing = rns_list.RnsListCommand().execute(ParsedCommand(path="rns/list"))
        result = rns_send.RnsSendCommand().execute(
            ParsedCommand(
                path="rns/send", positional=["1", "hello"], sender_phone="+47123"
            )
        )

        self.assertEqual("1. Alice", listing)
        self.assertEqual("Sent: Alice", result)
        self.assertEqual([(self.fake.destination, "hello")], self.fake.sent)
        self.assertEqual([("+47123", self.fake.destination)], self.fake.contexts)

    def test_use_and_reply(self):
        selected = rns_use.RnsUseCommand().execute(
            ParsedCommand(path="rns/use", positional=["1"], sender_phone="+47123")
        )
        replied = rns_reply.RnsReplyCommand().execute(
            ParsedCommand(
                path="rns/reply", positional=["hello", "again"], sender_phone="+47123"
            )
        )

        self.assertEqual("Using: Alice", selected)
        self.assertEqual("OK sent to Alice", replied)
        self.assertEqual([(self.fake.destination, "hello again")], self.fake.sent)


if __name__ == "__main__":
    unittest.main()


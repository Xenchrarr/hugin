import tempfile
import unittest
from pathlib import Path

from app.chat import ChatStore
from app.normalizer import NormalizedMessage


class _RawMessage:
    def __init__(self, message_hash: bytes, timestamp: int = 100):
        self.hash = message_hash
        self.timestamp = timestamp
        self.method = 2
        self.progress = 0.5
        self.transport_encrypted = True
        self.transport_encryption = "ratchet"
        self.signature_validated = True
        self.rssi = -90
        self.snr = 4.5
        self.q = 70

    @staticmethod
    def packed_container():
        return b"packed-lxmf"


class ChatStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = ChatStore(Path(self.directory.name) / "chat.sqlite3")

    def tearDown(self):
        self.directory.cleanup()

    def test_inbound_message_creates_thread_and_is_idempotent(self):
        message = NormalizedMessage(
            message_id="11" * 16,
            source_hash="aa" * 16,
            destination_hash="bb" * 16,
            sender_name="Alice",
            text="Hello from Alice",
            title="",
            timestamp=123,
            fields={},
        )
        raw = _RawMessage(bytes.fromhex(message.message_id), timestamp=123)

        first = self.store.record_inbound(message, raw)
        second = self.store.record_inbound(message, raw)

        self.assertEqual(first["message_hash"], second["message_hash"])
        conversations = self.store.conversations()
        self.assertEqual(1, len(conversations))
        self.assertEqual("Alice", conversations[0]["display_name"])
        self.assertEqual(1, conversations[0]["unread_count"])
        self.assertTrue(first["signature_validated"])
        self.assertTrue(first["transport_encrypted"])

    def test_outbound_message_supports_client_idempotency_and_state_updates(self):
        raw = _RawMessage(bytes.fromhex("22" * 16), timestamp=456)
        stored = self.store.record_outbound(
            raw,
            "cc" * 16,
            "On my way",
            "",
            "sending",
            "direct",
            "client-1",
        )

        self.assertEqual(stored, self.store.message_for_token("client-1"))
        self.store.update_outbound(raw, "delivered")
        updated = self.store.message(stored["message_hash"])
        self.assertIsNotNone(updated)
        self.assertEqual("delivered", updated["state"])
        self.assertEqual("On my way", self.store.conversations()[0]["last_text"])

    def test_mark_read_clears_unread_count(self):
        message = NormalizedMessage(
            message_id="33" * 16,
            source_hash="dd" * 16,
            destination_hash="ee" * 16,
            sender_name=None,
            text="Ping",
            title="",
            timestamp=789,
            fields={},
        )
        self.store.record_inbound(message, _RawMessage(bytes.fromhex(message.message_id)))

        self.store.mark_read(message.source_hash)

        self.assertEqual(0, self.store.conversations()[0]["unread_count"])

    def test_announce_stream_keeps_latest_destination_and_seen_count(self):
        first = self.store.record_announce(
            "ab" * 16,
            "cd" * 16,
            "lxmf.delivery",
            "Alice",
            None,
            2,
            "ef" * 16,
            False,
        )
        second = self.store.record_announce(
            "ab" * 16,
            "cd" * 16,
            "lxmf.delivery",
            "Alice Mobile",
            None,
            1,
            "12" * 16,
            False,
        )

        self.assertEqual(1, first["seen_count"])
        self.assertEqual(2, second["seen_count"])
        self.assertEqual("Alice Mobile", second["display_name"])
        self.assertEqual(1, second["hops"])
        self.assertEqual([second], self.store.announces(aspect="lxmf.delivery"))

    def test_announce_name_enriches_existing_conversation(self):
        destination = "ab" * 16
        raw = _RawMessage(bytes.fromhex("55" * 16), timestamp=456)
        self.store.record_outbound(raw, destination, "Hello", "", "sent", "direct")
        self.store.record_announce(
            destination, None, "lxmf.delivery", "Alice", None, 1, None, False
        )

        self.assertEqual("Alice", self.store.conversations()[0]["display_name"])
        self.assertEqual("Alice", self.store.display_name_for_destination(destination))


if __name__ == "__main__":
    unittest.main()

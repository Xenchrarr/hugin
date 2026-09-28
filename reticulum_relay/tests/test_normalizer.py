import unittest
from types import SimpleNamespace

from app.normalizer import normalize_lxmf


class NormalizerTests(unittest.TestCase):
    def test_normalizes_bytes_and_can_redact(self):
        raw = SimpleNamespace(
            hash=b"\x01" * 16,
            source_hash=b"\x02" * 16,
            destination_hash=b"\x03" * 16,
            source_display_name=b"Alice",
            content=b"secret 1234",
            title=b"Status",
            timestamp=123,
            fields={1: b"value"},
        )

        message = normalize_lxmf(raw)
        redacted = message.redacted(
            [{"field": "text", "pattern": r"\d+", "replace": "[PIN]"}]
        )

        self.assertEqual("01" * 16, message.message_id)
        self.assertEqual("02" * 16, message.source_hash)
        self.assertEqual("Alice", message.sender_name)
        self.assertEqual("secret [PIN]", redacted.text)


if __name__ == "__main__":
    unittest.main()


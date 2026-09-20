import unittest
from unittest.mock import patch

from src.sms_handler import SMSHandler


class SmsSendingTests(unittest.TestCase):
    @staticmethod
    def _handler():
        handler = SMSHandler.__new__(SMSHandler)
        handler.send_at = lambda command, timeout=3: "\r\nOK\r\n"
        return handler

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_gsm7_reserves_room_for_sacrificial_trailing_character(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )

        self.assertTrue(handler._send_sms_locked("+4712345678", "a" * 160))
        self.assertEqual([("a" * 159, True), ("a", True)], chunks)

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_ucs2_fallback_uses_69_code_unit_chunks(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )

        self.assertTrue(handler._send_sms_locked("+4712345678", "漢" * 70))
        self.assertEqual([("漢" * 69, False), ("漢", False)], chunks)

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_norwegian_conversation_list_uses_at_most_two_gsm7_parts(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )
        message = "\n".join(
            [
                "1. Ragnhild Ho>",
                "2. Sondre Meyer",
                "3. Svein Åge J>",
                "4. Ultra Old S>",
                "5. Emil Ramsdal",
                "6. Fredrik Ols>",
                "7. Nikolai Gre>",
                "8. Ragnhild, H>",
                "9. Håkon Hersk>",
                "10. Sommerferie>",
            ]
        )

        self.assertTrue(handler._send_sms_locked("+4712345678", message))
        self.assertLessEqual(len(chunks), 2)
        self.assertTrue(all(use_gsm7 for _, use_gsm7 in chunks))
        self.assertTrue(all(len(handler._gsm7_encode(chunk)) <= 159 for chunk, _ in chunks))
        self.assertEqual(message.split(), " ".join(chunk for chunk, _ in chunks).split())

    def test_gsm7_supports_norwegian_letters_and_counts_extension_septets(self):
        self.assertEqual(6, len(SMSHandler._gsm7_encode("ÅåÆæØø")))
        self.assertEqual(2, len(SMSHandler._gsm7_encode("[")))

    def test_ucs2_prefix_counts_non_bmp_characters_as_two_units(self):
        self.assertEqual(1, SMSHandler._encoded_prefix_end("a😀", 1, False))
        self.assertEqual(2, SMSHandler._encoded_prefix_end("a😀", 3, False))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_partial_multipart_failure_is_marked_uncertain(self, _sleep):
        handler = self._handler()
        outcomes = iter((True, False))
        handler._send_sms_chunk = lambda *_args: next(outcomes)

        self.assertFalse(handler._send_sms_locked("+4712345678", "a" * 160))
        self.assertTrue(handler._last_send_uncertain)


if __name__ == "__main__":
    unittest.main()

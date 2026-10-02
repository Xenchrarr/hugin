import unittest
from unittest.mock import Mock, patch

from src.sms_handler import SMSHandler


class SmsSendingTests(unittest.TestCase):
    @staticmethod
    def _handler():
        handler = SMSHandler.__new__(SMSHandler)
        handler.send_at = lambda command, timeout=3: "\r\nOK\r\n"
        return handler

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_gsm7_uses_full_160_septet_payload(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )

        self.assertTrue(handler._send_sms_locked("+4712345678", "a" * 160))
        self.assertEqual([("a" * 160, True)], chunks)

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_ucs2_fallback_uses_full_70_code_unit_payload(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )

        self.assertTrue(handler._send_sms_locked("+4712345678", "漢" * 70))
        self.assertEqual([("漢" * 70, False)], chunks)

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
        self.assertTrue(all(len(handler._gsm7_encode(chunk)) <= 160 for chunk, _ in chunks))
        self.assertEqual(message.split(), " ".join(chunk for chunk, _ in chunks).split())

    def test_gsm7_supports_norwegian_letters_and_counts_extension_septets(self):
        self.assertEqual(6, len(SMSHandler._gsm7_encode("ÅåÆæØø")))
        self.assertEqual(2, len(SMSHandler._gsm7_encode("[")))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_plain_telegram_group_message_stays_in_one_gsm7_part(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )
        message = "Family / Alice: " + "a" * 80

        self.assertTrue(handler._send_sms_locked("+4712345678", message))
        self.assertEqual([(message, True)], chunks)

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_gsm_extension_character_uses_ucs2_to_avoid_escape_cancelling_cmgs(
        self, _sleep
    ):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda number, chunk, use_gsm7: chunks.append((number, chunk, use_gsm7))
            or True
        )

        self.assertTrue(handler._send_sms_locked("+4712345678", "power | energy"))
        self.assertEqual(
            [("002B0034003700310032003300340035003600370038", "power | energy", False)],
            chunks,
        )

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_cmgs_requires_submission_reference_not_bare_ok(self, _sleep):
        handler = SMSHandler.__new__(SMSHandler)
        handler.ser = Mock()
        handler.flush_serial = Mock()
        handler._read_until = Mock(side_effect=[">", "\r\nOK\r\n"])

        self.assertFalse(handler._send_sms_chunk("+4712345678", "hello", True))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_cmgs_accepts_submission_reference_followed_by_ok(self, _sleep):
        handler = SMSHandler.__new__(SMSHandler)
        handler.ser = Mock()
        handler.flush_serial = Mock()
        handler._read_until = Mock(
            side_effect=[">", "\r\n+CMGS: 42\r\n\r\nOK\r\n"]
        )

        self.assertTrue(handler._send_sms_chunk("+4712345678", "hello", True))

    def test_ucs2_prefix_counts_non_bmp_characters_as_two_units(self):
        self.assertEqual(1, SMSHandler._encoded_prefix_end("a😀", 1, False))
        self.assertEqual(2, SMSHandler._encoded_prefix_end("a😀", 3, False))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_long_routed_message_repeats_label_reference_and_part_number(self, sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )
        body = "word " * 80

        self.assertTrue(handler._send_sms_locked("+4712345678", f"(tg/nikolai #184)\n{body}"))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(use_gsm7 for _, use_gsm7 in chunks))
        self.assertTrue(all(len(handler._gsm7_encode(chunk)) <= 160 for chunk, _ in chunks))
        self.assertTrue(chunks[0][0].startswith(f"(tg/nikolai #184 1/{len(chunks)})\n"))
        self.assertTrue(chunks[-1][0].startswith(
            f"(tg/nikolai #184 {len(chunks)}/{len(chunks)})\n"
        ))
        restored = "".join(chunk.split("\n", 1)[1] for chunk, _ in chunks)
        self.assertEqual(body, restored)
        self.assertEqual(len(chunks) - 1, sleep.call_count)
        sleep.assert_called_with(2.0)

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_single_part_message_does_not_wait(self, sleep):
        handler = self._handler()
        handler._send_sms_chunk = lambda *_args: True

        self.assertTrue(handler._send_sms_locked("+4712345678", "hello"))

        sleep.assert_not_called()

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_unicode_routed_message_parts_fit_ucs2_capacity(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )
        body = "漢字" * 80

        self.assertTrue(handler._send_sms_locked("+4712345678", f"(tg/family #9)\n{body}"))
        self.assertTrue(all(not use_gsm7 for _, use_gsm7 in chunks))
        self.assertTrue(all(len(chunk.encode("utf-16-be")) // 2 <= 70 for chunk, _ in chunks))
        self.assertEqual(body, "".join(chunk.split("\n", 1)[1] for chunk, _ in chunks))

    def test_maximum_alias_and_reference_still_leave_unicode_part_capacity(self):
        message = (
            "(abcdefghij/abcdefghijklmnopqr #9223372036854775807)\n" + "漢" * 20
        )
        chunks = SMSHandler._split_outbound_text(message, 70, False)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.startswith("(abcdefghij/abcdefghijklmnopqr #9223372036854775807 ")
                            for chunk in chunks))
        self.assertTrue(all(len(chunk.encode("utf-16-be")) // 2 <= 70 for chunk in chunks))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_long_system_response_repeats_hub_label(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = lambda _number, chunk, _gsm: chunks.append(chunk) or True

        self.assertTrue(handler._send_sms_locked("+4712345678", "(hub) " + "chat " * 80))

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.startswith("(hub ") for chunk in chunks))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_legacy_bracketed_route_is_normalized_to_gsm7(self, _sleep):
        handler = self._handler()
        chunks = []
        handler._send_sms_chunk = (
            lambda _number, chunk, use_gsm7: chunks.append((chunk, use_gsm7)) or True
        )

        self.assertTrue(handler._send_sms_locked(
            "+4712345678", "[tg/family #184]\nAlice: Hello"
        ))

        self.assertEqual([("(tg/family #184)\nAlice: Hello", True)], chunks)

    def test_long_token_does_not_create_a_tiny_routed_part(self):
        message = "(tg/family #184)\nAlice: " + "a" * 150

        chunks = SMSHandler._split_outbound_text(message, 160, True)

        self.assertGreater(len(chunks[0].split("\n", 1)[1]), 100)
        self.assertTrue(all(len(SMSHandler._gsm7_encode(chunk)) <= 160 for chunk in chunks))

    @patch("src.sms_handler.time.sleep", return_value=None)
    def test_partial_multipart_failure_is_marked_uncertain(self, _sleep):
        handler = self._handler()
        outcomes = iter((True, False))
        handler._send_sms_chunk = lambda *_args: next(outcomes)

        self.assertFalse(handler._send_sms_locked("+4712345678", "a" * 161))
        self.assertTrue(handler._last_send_uncertain)


if __name__ == "__main__":
    unittest.main()

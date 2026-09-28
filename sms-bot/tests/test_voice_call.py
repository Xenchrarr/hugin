import threading
import unittest
from unittest.mock import Mock, patch

from src.api import sms_api
from src.sms_handler import SMSHandler
from src.call_handler import CallHandler


class VoiceCallTests(unittest.TestCase):
    def _handler(self, call_states):
        handler = SMSHandler.__new__(SMSHandler)
        handler._modem_lock = threading.RLock()
        handler.ser = Mock()
        handler.flush_serial = Mock()
        handler._read_until = Mock(return_value="\r\nOK\r\n")
        handler.send_at_no_flush = Mock(side_effect=[*call_states, "\r\nOK\r\n"])
        calls = CallHandler(handler)
        calls._wait_for_voice_registration = Mock(return_value=True)
        return calls

    @patch("src.call_handler.time.sleep", return_value=None)
    def test_ring_call_hangs_up_when_answered(self, _sleep):
        handler = self._handler([
            '+CLCC: 1,0,3,0,0,"+4712345678",145\r\nOK',
            '+CLCC: 1,0,0,0,0,"+4712345678",145\r\nOK',
        ])

        result = handler.ring_call("+4712345678", 20)

        self.assertTrue(result["ok"])
        self.assertEqual("answered", result["status"])
        handler.modem.ser.write.assert_called_once_with(b"ATD+4712345678;\r")
        self.assertEqual("ATH", handler.modem.send_at_no_flush.call_args_list[-1].args[0])

    @patch("src.call_handler.time.sleep", return_value=None)
    def test_ring_call_hangs_up_after_timeout(self, _sleep):
        handler = self._handler([
            '+CLCC: 1,0,3,0,0,"+4712345678",145\r\nOK'
            for _ in range(5)
        ])

        result = handler.ring_call("+4712345678", 5)

        self.assertTrue(result["ok"])
        self.assertEqual("ring_timeout", result["status"])
        self.assertEqual("ATH", handler.modem.send_at_no_flush.call_args_list[-1].args[0])

    @patch("src.call_handler.time.sleep", return_value=None)
    def test_ring_call_tolerates_a_transient_empty_call_list(self, _sleep):
        handler = self._handler([
            '+CLCC: 1,0,3,0,0,"+4712345678",145\r\nOK',
            "\r\nOK\r\n",
            *[
                '+CLCC: 1,0,3,0,0,"+4712345678",145\r\nOK'
                for _ in range(4)
            ],
        ])

        result = handler.ring_call("+4712345678", 5)

        self.assertTrue(result["ok"])
        self.assertEqual("ring_timeout", result["status"])
        self.assertEqual(7, handler.modem.send_at_no_flush.call_count)


class VoiceCallApiTests(unittest.TestCase):
    def setUp(self):
        self.original_handler = sms_api._sms_handler
        self.original_call_handler = sms_api._call_handler
        self.original_key = sms_api._SERVICE_KEY
        sms_api._SERVICE_KEY = "test-key"

    def tearDown(self):
        sms_api._sms_handler = self.original_handler
        sms_api._call_handler = self.original_call_handler
        sms_api._SERVICE_KEY = self.original_key

    def test_ring_endpoint_requires_auth_and_e164_number(self):
        client = sms_api._app.test_client()
        unauthorized = client.post("/api/calls/ring", json={"phone": "+4712345678"})
        invalid = client.post(
            "/api/calls/ring",
            json={"phone": "ATD123;"},
            headers={"X-Service-Key": "test-key"},
        )

        self.assertEqual(401, unauthorized.status_code)
        self.assertEqual(400, invalid.status_code)

    def test_ring_endpoint_calls_modem(self):
        handler = Mock()
        handler.ring_call.return_value = {"ok": True, "status": "ring_timeout"}
        sms_api._call_handler = handler

        response = sms_api._app.test_client().post(
            "/api/calls/ring",
            json={"phone": "+4712345678", "ring_seconds": 12},
            headers={"X-Service-Key": "test-key"},
        )

        self.assertEqual(200, response.status_code)
        handler.ring_call.assert_called_once_with("+4712345678", 12)


if __name__ == "__main__":
    unittest.main()

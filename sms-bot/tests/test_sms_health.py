import threading
import tempfile
import unittest
from pathlib import Path

from src.sms_handler import SMSHandler
from src.api import sms_api
from src.delivery_ledger import DeliveryLedger


class SmsHealthTests(unittest.TestCase):
    def _handler(self, responses):
        handler = SMSHandler.__new__(SMSHandler)
        handler._modem_lock = threading.RLock()
        handler._last_successful_send = None
        handler._last_send_error = ""
        handler.send_at = lambda command, timeout=3: responses[command]
        return handler

    def test_ready_when_modem_sim_and_network_are_ready(self):
        handler = self._handler({
            "AT": "\r\nOK\r\n",
            "AT+CPIN?": "+CPIN: READY\r\nOK",
            "AT+CEREG?": "+CEREG: 0,1\r\nOK",
            "AT+CSQ": "+CSQ: 21,99\r\nOK",
        })
        result = handler.get_health()
        self.assertTrue(result["ready"])
        self.assertEqual(21, result["signal"])

    def test_not_ready_when_network_is_searching(self):
        handler = self._handler({
            "AT": "\r\nOK\r\n",
            "AT+CPIN?": "+CPIN: READY\r\nOK",
            "AT+CEREG?": "+CEREG: 0,2\r\nOK",
            "AT+CSQ": "+CSQ: 12,99\r\nOK",
        })
        result = handler.get_health()
        self.assertFalse(result["ready"])
        self.assertFalse(result["network"])


class SmsApiFailureTests(unittest.TestCase):
    def setUp(self):
        self.original_handler = sms_api._sms_handler
        self.original_key = sms_api._SERVICE_KEY
        self.original_ledger = sms_api._delivery_ledger
        self.temp_dir = tempfile.TemporaryDirectory()
        sms_api._delivery_ledger = DeliveryLedger(
            str(Path(self.temp_dir.name) / "receipts.sqlite3")
        )
        sms_api._SERVICE_KEY = "test-key"

    def tearDown(self):
        sms_api._sms_handler = self.original_handler
        sms_api._SERVICE_KEY = self.original_key
        sms_api._delivery_ledger = self.original_ledger
        self.temp_dir.cleanup()

    def test_failed_modem_send_is_not_reported_as_success(self):
        class FailingHandler:
            @staticmethod
            def send_sms(phone, message):
                return False

        sms_api._sms_handler = FailingHandler()
        client = sms_api._app.test_client()
        response = client.post(
            "/api/sms/send",
            json={
                "phone": "+4712345678",
                "message": "hello",
                "delivery_token": "delivery-1",
            },
            headers={"X-Service-Key": "test-key"},
        )
        self.assertEqual(503, response.status_code)
        self.assertIn("did not accept", response.get_json()["error"])

    def test_sms_send_requires_service_key(self):
        class Handler:
            @staticmethod
            def send_sms(phone, message):
                raise AssertionError("unauthenticated request reached the modem")

        sms_api._sms_handler = Handler()
        client = sms_api._app.test_client()

        response = client.post(
            "/api/sms/send",
            json={"phone": "+4712345678", "message": "hello"},
        )

        self.assertEqual(401, response.status_code)
        self.assertIn("service key", response.get_json()["error"].lower())

    def test_mms_send_requires_service_key(self):
        client = sms_api._app.test_client()

        response = client.post(
            "/api/sms/mms/send",
            json={
                "phone": "+4712345678",
                "media_data": "anBlZw==",
                "media_mime_type": "image/jpeg",
                "delivery_token": "delivery-2",
            },
        )

        self.assertEqual(401, response.status_code)

    def test_mms_send_rejects_invalid_base64_and_media_type(self):
        client = sms_api._app.test_client()
        headers = {"X-Service-Key": "test-key"}

        invalid_data = client.post(
            "/api/sms/mms/send",
            json={
                "phone": "+4712345678",
                "media_data": "not base64!",
                "media_mime_type": "image/jpeg",
                "delivery_token": "delivery-bad-data",
            },
            headers=headers,
        )
        invalid_type = client.post(
            "/api/sms/mms/send",
            json={
                "phone": "+4712345678",
                "media_data": "anBlZw==",
                "media_mime_type": "application/pdf",
                "delivery_token": "delivery-3",
            },
            headers=headers,
        )

        self.assertEqual(400, invalid_data.status_code)
        self.assertEqual(400, invalid_type.status_code)

    def test_valid_mms_is_passed_to_modem(self):
        calls = []

        class Handler:
            @staticmethod
            def send_mms(phone, message, media_bytes, media_mime_type):
                calls.append((phone, message, media_bytes, media_mime_type))
                return True

        sms_api._sms_handler = Handler()
        client = sms_api._app.test_client()
        response = client.post(
            "/api/sms/mms/send",
            json={
                "phone": "+4712345678",
                "message": "Camera",
                "media_data": "anBlZw==",
                "media_mime_type": "image/jpeg",
                "delivery_token": "delivery-4",
            },
            headers={"X-Service-Key": "test-key"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [("+4712345678", "Camera", b"jpeg", "image/jpeg")], calls
        )

    def test_accepted_token_returns_cached_success_without_resending(self):
        calls = []

        class Handler:
            last_send_uncertain = False

            @staticmethod
            def send_sms(phone, message):
                calls.append((phone, message))
                return True

        sms_api._sms_handler = Handler()
        client = sms_api._app.test_client()
        request = {
            "phone": "+4712345678",
            "message": "hello",
            "delivery_token": "delivery-5",
        }

        first = client.post(
            "/api/sms/send", json=request, headers={"X-Service-Key": "test-key"}
        )
        second = client.post(
            "/api/sms/send", json=request, headers={"X-Service-Key": "test-key"}
        )

        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertTrue(second.get_json()["duplicate"])
        self.assertEqual([("+4712345678", "hello")], calls)

    def test_ambiguous_modem_failure_is_not_automatically_retried(self):
        calls = []

        class Handler:
            last_send_uncertain = True

            @staticmethod
            def send_sms(phone, message):
                calls.append((phone, message))
                return False

        sms_api._sms_handler = Handler()
        client = sms_api._app.test_client()
        request = {
            "phone": "+4712345678",
            "message": "hello",
            "delivery_token": "delivery-6",
        }

        first = client.post(
            "/api/sms/send", json=request, headers={"X-Service-Key": "test-key"}
        )
        second = client.post(
            "/api/sms/send", json=request, headers={"X-Service-Key": "test-key"}
        )

        self.assertEqual(409, first.status_code)
        self.assertEqual("uncertain", second.get_json()["delivery_state"])
        self.assertEqual([("+4712345678", "hello")], calls)


if __name__ == "__main__":
    unittest.main()

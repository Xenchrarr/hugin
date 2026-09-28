import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.services.external.phone_call_job_service import run_phone_call


class PhoneCallJobServiceTests(unittest.TestCase):
    @patch("src.services.external.phone_call_job_service.DatabaseLogger")
    @patch("src.services.external.phone_call_job_service.ring_phone")
    @patch("src.services.external.phone_call_job_service.UserStorage")
    def test_calls_registered_user(self, storage_type, ring, _logger):
        storage_type.return_value.get_user.return_value = Mock(
            phone_number="+4712345678", display_name="Emil", username="emil",
        )
        ring.return_value = {"ok": True, "status": "ring_timeout"}

        result = run_phone_call('{"target":"7","ring_seconds":25}')

        self.assertEqual("ring_timeout", result["status"])
        storage_type.return_value.get_user.assert_called_once_with(7)
        ring.assert_called_once_with("+4712345678", ring_seconds=25)

    @patch("src.services.external.phone_call_job_service.DatabaseLogger")
    @patch("src.services.external.phone_call_job_service.ring_phone")
    @patch("src.services.external.phone_call_job_service.UserStorage")
    def test_accepts_explicit_e164_target(self, _storage_type, ring, _logger):
        ring.return_value = {"ok": True, "status": "answered"}
        run_phone_call("+4740142990")
        ring.assert_called_once_with("+4740142990", ring_seconds=20)

    @patch("src.services.external.phone_call_job_service.DatabaseLogger")
    @patch("src.services.external.phone_call_job_service.ring_phone")
    @patch("src.services.external.phone_call_job_service.UserStorage")
    def test_failed_call_fails_job(self, _storage_type, ring, _logger):
        ring.return_value = {"ok": False, "status": "ended"}
        with self.assertRaisesRegex(RuntimeError, "ended"):
            run_phone_call('{"phone":"+4740142990"}')

    def test_rejects_invalid_ring_seconds(self):
        with self.assertRaisesRegex(ValueError, "between 5 and 60"):
            run_phone_call('{"phone":"+4740142990","ring_seconds":2}')


if __name__ == "__main__":
    unittest.main()

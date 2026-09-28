import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask


src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.controllers.call_controller import call_blueprint


class CallControllerTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(call_blueprint, url_prefix="/calls")
        self.client = app.test_client()
        self.auth_patch = patch(
            "src.auth.decode_token",
            return_value={"sub": "7", "username": "alice", "is_admin": False},
        )
        self.auth_patch.start()

    def tearDown(self):
        self.auth_patch.stop()

    @staticmethod
    def _headers():
        return {"Authorization": "Bearer user-token"}

    @patch("src.controllers.call_controller.ring_phone")
    @patch("src.controllers.call_controller.UserStorage")
    def test_call_me_uses_authenticated_users_phone(self, storage_type, ring_phone):
        storage_type.return_value.get_user.return_value = Mock(phone_number="+4712345678")
        ring_phone.return_value = {"ok": True, "status": "ring_timeout"}

        response = self.client.post("/calls/me", headers=self._headers())

        self.assertEqual(200, response.status_code)
        storage_type.return_value.get_user.assert_called_once_with(7)
        ring_phone.assert_called_once_with("+4712345678", ring_seconds=20)

    @patch("src.controllers.call_controller.UserStorage")
    def test_call_me_requires_registered_phone(self, storage_type):
        storage_type.return_value.get_user.return_value = Mock(phone_number=None)

        response = self.client.post("/calls/me", headers=self._headers())

        self.assertEqual(400, response.status_code)
        self.assertIn("phone number", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()

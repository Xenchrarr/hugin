import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask


src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.controllers.reticulum_chat_controller import reticulum_chat_blueprint


class ReticulumChatControllerTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(reticulum_chat_blueprint, url_prefix="/reticulum-chat")
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

    def test_requires_authenticated_user(self):
        response = self.client.get("/reticulum-chat/conversations")

        self.assertEqual(401, response.status_code)

    @patch("src.controllers.reticulum_chat_controller.requests.request")
    def test_forwards_conversation_request_to_relay(self, request):
        relay_response = Mock(status_code=200)
        relay_response.json.return_value = [{"destination_hash": "ab" * 16}]
        request.return_value = relay_response

        response = self.client.get(
            "/reticulum-chat/conversations?limit=25", headers=self._headers()
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("ab" * 16, response.get_json()[0]["destination_hash"])
        _, kwargs = request.call_args
        self.assertEqual({"limit": "25"}, kwargs["params"])
        self.assertIn("X-Service-Key", kwargs["headers"])

    @patch("src.controllers.reticulum_chat_controller.requests.request")
    def test_forwards_send_payload_and_status(self, request):
        relay_response = Mock(status_code=202)
        relay_response.json.return_value = {"message_hash": "12" * 16, "state": "queued"}
        request.return_value = relay_response
        payload = {
            "destination_hash": "ab" * 16,
            "text": "hello",
            "delivery_method": "direct",
            "client_token": "web-1",
        }

        response = self.client.post(
            "/reticulum-chat/messages", json=payload, headers=self._headers()
        )

        self.assertEqual(202, response.status_code)
        self.assertEqual(payload, request.call_args.kwargs["json"])

    @patch("src.controllers.reticulum_chat_controller.requests.request")
    def test_unavailable_relay_returns_bad_gateway(self, request):
        request.side_effect = __import__("requests").ConnectionError()

        response = self.client.get("/reticulum-chat/status", headers=self._headers())

        self.assertEqual(502, response.status_code)
        self.assertIn("unavailable", response.get_json()["message"])

    @patch("src.controllers.reticulum_chat_controller.requests.request")
    def test_forwards_announce_stream_and_manual_announce(self, request):
        stream_response = Mock(status_code=200)
        stream_response.json.return_value = [{"destination_hash": "ab" * 16}]
        announce_response = Mock(status_code=200)
        announce_response.json.return_value = {"targets": [{"target": "delivery"}]}
        request.side_effect = [stream_response, announce_response]

        stream = self.client.get(
            "/reticulum-chat/announces?aspect=lxmf.delivery", headers=self._headers()
        )
        announce = self.client.post(
            "/reticulum-chat/announce",
            json={"target": "delivery"},
            headers=self._headers(),
        )

        self.assertEqual(200, stream.status_code)
        self.assertEqual(200, announce.status_code)
        self.assertEqual(
            {"limit": "100", "aspect": "lxmf.delivery"},
            request.call_args_list[0].kwargs["params"],
        )
        self.assertEqual(
            {"target": "delivery"}, request.call_args_list[1].kwargs["json"]
        )


if __name__ == "__main__":
    unittest.main()

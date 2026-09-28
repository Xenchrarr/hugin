import tempfile
import unittest
from pathlib import Path

from app.api import create_app
from app.state import StateStore


class _Node:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"status": "ok", "ready": True}

    def send(self, destination_hash, text, title, method):
        self.calls.append((destination_hash, text, title, method))
        return "message-1"

    @staticmethod
    def _parse_hash(value):
        if len(value) != 32:
            raise ValueError("bad hash")
        return bytes.fromhex(value)


class _Dispatcher:
    @staticmethod
    def reload():
        return 2


class ApiTests(unittest.TestCase):
    def test_send_is_authenticated_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            state = StateStore(Path(directory) / "state.json")
            node = _Node()
            client = create_app(node, state, _Dispatcher(), "secret").test_client()
            body = {
                "destination_hash": "ab" * 16,
                "text": "hello",
                "delivery_token": "token-1",
            }

            self.assertEqual(401, client.post("/api/reticulum/send", json=body).status_code)
            first = client.post(
                "/api/reticulum/send",
                json=body,
                headers={"X-Service-Key": "secret"},
            )
            second = client.post(
                "/api/reticulum/send",
                json=body,
                headers={"X-Service-Key": "secret"},
            )

        self.assertEqual(202, first.status_code)
        self.assertTrue(second.get_json()["duplicate"])
        self.assertEqual(1, len(node.calls))


if __name__ == "__main__":
    unittest.main()


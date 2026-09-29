import tempfile
import unittest
from pathlib import Path

from app.api import create_app
from app.state import StateStore


class _Node:
    def __init__(self, chat=None):
        self.calls = []
        self.chat = chat

    def status(self):
        return {"status": "ok", "ready": True}

    @staticmethod
    def announce(target):
        return {"announced_at": 123, "targets": [{"target": target}]}

    def send(self, destination_hash, text, title, method, client_token=""):
        self.calls.append((destination_hash, text, title, method, client_token))
        if self.chat is not None:
            self.chat.record_outbound(
                type(
                    "RawMessage",
                    (),
                    {
                        "hash": bytes.fromhex("11" * 16),
                        "timestamp": 123,
                        "method": 2,
                        "progress": 0,
                        "packed_container": lambda self: b"packed",
                    },
                )(),
                destination_hash,
                text,
                title,
                "queued",
                method,
                client_token,
            )
            return "11" * 16
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

    def test_chat_send_and_conversation_history(self):
        from app.chat import ChatStore

        with tempfile.TemporaryDirectory() as directory:
            state = StateStore(Path(directory) / "state.json")
            chat = ChatStore(Path(directory) / "chat.sqlite3")
            node = _Node(chat)
            client = create_app(node, state, _Dispatcher(), "secret", chat).test_client()
            headers = {"X-Service-Key": "secret"}
            body = {
                "destination_hash": "ab" * 16,
                "text": "hello",
                "delivery_method": "direct",
                "client_token": "web-1",
            }

            sent = client.post("/api/reticulum/chat/messages", json=body, headers=headers)
            messages = client.get(
                f"/api/reticulum/chat/conversations/{'ab' * 16}/messages",
                headers=headers,
            )
            conversations = client.get(
                "/api/reticulum/chat/conversations", headers=headers
            )

        self.assertEqual(202, sent.status_code)
        self.assertEqual("hello", sent.get_json()["text"])
        self.assertEqual("web-1", sent.get_json()["client_token"])
        self.assertEqual(1, len(messages.get_json()))
        self.assertEqual("ab" * 16, conversations.get_json()[0]["destination_hash"])

    def test_lists_announces_and_triggers_manual_announce(self):
        from app.chat import ChatStore

        with tempfile.TemporaryDirectory() as directory:
            state = StateStore(Path(directory) / "state.json")
            chat = ChatStore(Path(directory) / "chat.sqlite3")
            chat.record_announce(
                "ab" * 16, None, "nomadnetwork.node", "Field Site", None, 1, None, False
            )
            client = create_app(_Node(), state, _Dispatcher(), "secret", chat).test_client()
            headers = {"X-Service-Key": "secret"}

            listing = client.get("/api/reticulum/announces", headers=headers)
            announced = client.post(
                "/api/reticulum/announce",
                json={"target": "site"},
                headers=headers,
            )

        self.assertEqual("Field Site", listing.get_json()[0]["display_name"])
        self.assertEqual("site", announced.get_json()["targets"][0]["target"])


if __name__ == "__main__":
    unittest.main()

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


base_module = types.ModuleType("app.destinations.base")


class _AbstractDestination:
    pass


base_module.AbstractDestination = _AbstractDestination
sys.modules.setdefault("app.destinations.base", base_module)

module_path = Path(__file__).resolve().parents[1] / "app" / "destinations" / "reticulum.py"
spec = importlib.util.spec_from_file_location("reticulum_destination_under_test", module_path)
reticulum_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(reticulum_module)
ReticulumAdapter = reticulum_module.ReticulumAdapter


class ReticulumDestinationTests(unittest.TestCase):
    @patch.object(reticulum_module.httpx, "AsyncClient")
    def test_queues_delivery_for_destination_hash(self, client_type):
        response = AsyncMock()
        response.raise_for_status = lambda: None
        client = AsyncMock()
        client.is_closed = False
        client.post.return_value = response
        client_type.return_value = client
        adapter = ReticulumAdapter(
            "17", {"destination_hash": "ab" * 16, "delivery_method": "opportunistic"}
        )

        asyncio.run(adapter.send({
            "chat_id": 42,
            "message_id": 7,
            "chat_title": "Family",
            "sender_name": "Alice",
            "chat_type": "group",
            "text": "Hello",
        }))

        body = client.post.call_args.kwargs["json"]
        delivery = body["deliveries"][0]
        self.assertEqual("reticulum-main", delivery["gateway_key"])
        self.assertEqual("ab" * 16, delivery["address"]["destination_hash"])
        self.assertEqual("opportunistic", delivery["address"]["delivery_method"])
        self.assertEqual("Family / Alice: Hello", body["payload"]["text"])


if __name__ == "__main__":
    unittest.main()

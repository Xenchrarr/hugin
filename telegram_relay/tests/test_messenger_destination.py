import asyncio
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


# Another relay test replaces app.config while isolating the TDLib wrapper.
# Load this adapter directly so discovery order cannot leak that stub here.
module_path = Path(__file__).resolve().parents[1] / "app" / "destinations" / "messenger.py"
spec = importlib.util.spec_from_file_location("messenger_destination_under_test", module_path)
messenger_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(messenger_module)
MessengerAdapter = messenger_module.MessengerAdapter


class MessengerDestinationTests(unittest.TestCase):
    @patch.object(messenger_module.httpx, "AsyncClient")
    def test_queues_delivery_for_configured_thread(self, client_type):
        response = AsyncMock()
        response.raise_for_status = lambda: None
        client = AsyncMock()
        client.is_closed = False
        client.post.return_value = response
        client_type.return_value = client
        adapter = MessengerAdapter("17", {"thread_id": "9988"})

        asyncio.run(adapter.send({
            "chat_id": 42,
            "message_id": 7,
            "chat_title": "Family",
            "sender_name": "Alice",
            "chat_type": "group",
            "text": "Hello",
        }))

        body = client.post.call_args.kwargs["json"]
        self.assertEqual("messenger-main", body["deliveries"][0]["gateway_key"])
        self.assertEqual({"thread_id": "9988"}, body["deliveries"][0]["address"])
        self.assertEqual("Family / Alice: Hello", body["payload"]["text"])
        self.assertEqual(17, body["deliveries"][0]["target_endpoint_id"])


if __name__ == "__main__":
    unittest.main()

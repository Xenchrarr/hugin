import asyncio
import unittest

from app.models import NormalizedMessage
from app.routing import RouteDispatcher, Target, compile_routes, matches_condition


class _Response:
    def raise_for_status(self):
        return None


class _Client:
    def __init__(self):
        self.calls = []

    async def post(self, url, json):
        self.calls.append((url, json))
        return _Response()


class RoutingTests(unittest.TestCase):
    def test_compiles_only_routes_for_messenger_source(self):
        raw = {
            "endpoints": [
                {"id": 1, "key": "messenger-main", "type": "messenger", "capabilities": ["source"]},
                {"id": 2, "key": "phone", "type": "sms", "capabilities": ["target"], "config": {"phone": "+47"}},
            ],
            "routes": [
                {
                    "id": 9,
                    "key": "messenger-phone",
                    "enabled": True,
                    "sources": [{"key": "messenger-main"}],
                    "targets": [{"endpoint": {"id": 2}, "enabled": True, "transform": {}}],
                },
                {
                    "id": 10,
                    "key": "telegram-phone",
                    "enabled": True,
                    "sources": [{"key": "telegram-main"}],
                    "targets": [{"endpoint": {"id": 2}, "enabled": True}],
                },
            ],
        }

        routes = compile_routes(raw, "messenger-main")

        self.assertEqual(1, len(routes))
        self.assertEqual("sms", routes[0].targets[0].endpoint_type)
        self.assertEqual(9, routes[0].targets[0].route_id)

    def test_condition_engine_handles_string_thread_ids(self):
        message = NormalizedMessage(
            message_id="$1",
            chat_id="123",
            chat_title="Family",
            chat_type="group",
            sender_id="42",
            sender_name="Alice",
            text="critical alert",
            media_type=None,
            caption=None,
            timestamp=1,
            room_id="!room:test",
        )
        condition = {
            "all": [
                {"field": "chat_id", "op": "eq", "value": 123},
                {"field": "text", "op": "regex", "value": "(?i)alert"},
            ]
        }
        self.assertTrue(matches_condition(condition, message))

    def test_sms_payload_includes_messenger_source_prefix(self):
        message = NormalizedMessage(
            message_id="$1",
            chat_id="123",
            chat_title="Family",
            chat_type="group",
            sender_id="42",
            sender_name="Alice",
            text="Hello",
            media_type=None,
            caption=None,
            timestamp=1,
            room_id="!room:test",
        )
        target = Target(
            endpoint_id="2",
            endpoint_key="phone",
            endpoint_type="sms",
            config={"phone": "+47"},
            transform={},
            route_id=9,
        )
        dispatcher = RouteDispatcher.__new__(RouteDispatcher)
        dispatcher._base = "http://orchestrator:6000"
        dispatcher._client = _Client()

        asyncio.run(dispatcher.dispatch(message, target))

        _, body = dispatcher._client.calls[0]
        self.assertEqual("fb: Family / Alice: Hello", body["payload"]["text"])


if __name__ == "__main__":
    unittest.main()

import unittest

from app.models import NormalizedMessage
from app.routing import compile_routes, matches_condition


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


if __name__ == "__main__":
    unittest.main()

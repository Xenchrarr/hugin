import unittest

from app.normalizer import NormalizedMessage
from app.routing import compile_routes, matches_condition


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.message = NormalizedMessage(
            message_id="01" * 16,
            source_hash="02" * 16,
            destination_hash="03" * 16,
            sender_name="Alice",
            text="Cabin alarm",
            title="Alert",
            timestamp=123,
            fields={},
        )

    def test_compiles_only_reticulum_source_routes(self):
        raw = {
            "endpoints": [
                {"id": 1, "key": "reticulum-main", "type": "reticulum", "capabilities": ["source"]},
                {"id": 2, "key": "phone", "type": "sms", "capabilities": ["target"], "config": {"phone": "+47"}},
            ],
            "routes": [
                {
                    "id": 9,
                    "name": "RNS to phone",
                    "sources": [{"id": 1, "key": "reticulum-main"}],
                    "targets": [{"endpoint": {"id": 2}, "transform": {"redact": []}}],
                },
                {
                    "id": 10,
                    "name": "Telegram only",
                    "sources": [{"key": "telegram-main"}],
                    "targets": [{"endpoint": {"id": 2}}],
                },
            ],
        }

        routes = compile_routes(raw, "reticulum-main")

        self.assertEqual(1, len(routes))
        self.assertEqual("sms", routes[0].targets[0].endpoint_type)
        self.assertEqual(9, routes[0].targets[0].route_id)

    def test_matches_common_filter_operators(self):
        self.assertTrue(
            matches_condition(
                {"all": [
                    {"field": "sender_name", "op": "eq", "value": "Alice"},
                    {"field": "text", "op": "contains", "value": "alarm"},
                ]},
                self.message,
            )
        )
        self.assertFalse(
            matches_condition(
                {"field": "title", "op": "regex", "value": "^Info"}, self.message
            )
        )


if __name__ == "__main__":
    unittest.main()


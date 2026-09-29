import unittest
from unittest.mock import Mock, patch

from app.normalizer import NormalizedMessage
from app.routing import RouteDispatcher, Target, compile_routes, matches_condition


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

    @patch("app.routing.requests.post")
    def test_sms_payload_includes_reticulum_source_prefix(self, post):
        post.return_value.raise_for_status.return_value = None
        target = Target(
            endpoint_id=2,
            endpoint_key="phone",
            endpoint_type="sms",
            config={"phone": "+47"},
            transform={},
            route_id=9,
        )
        dispatcher = RouteDispatcher.__new__(RouteDispatcher)
        dispatcher._base = "http://orchestrator:6000"
        dispatcher._headers = {}
        dispatcher._state = Mock()

        dispatcher._submit(self.message, target)

        body = post.call_args.kwargs["json"]
        self.assertEqual("rns: Alice: Cabin alarm", body["payload"]["text"])


if __name__ == "__main__":
    unittest.main()

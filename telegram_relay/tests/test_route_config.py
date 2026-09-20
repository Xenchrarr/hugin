import unittest

from app.routing_config import compile_routes


class RouteConfigTests(unittest.TestCase):
    def test_one_route_fans_out_to_every_enabled_target(self):
        config = {
            "endpoints": [
                {
                    "id": 1,
                    "key": "telegram-main",
                    "name": "Telegram",
                    "type": "telegram",
                    "enabled": True,
                    "capabilities": ["source", "target"],
                    "config": {},
                },
                {
                    "id": 2,
                    "key": "phone",
                    "name": "Phone",
                    "type": "sms",
                    "enabled": True,
                    "capabilities": ["target"],
                    "config": {"phone": "+4712345678"},
                },
                {
                    "id": 3,
                    "key": "archive",
                    "name": "Archive",
                    "type": "webhook",
                    "enabled": True,
                    "capabilities": ["target"],
                    "config": {"url": "https://example.invalid/hook"},
                },
            ],
            "routes": [
                {
                    "key": "telegram-everywhere",
                    "name": "Telegram everywhere",
                    "enabled": True,
                    "match_all_sources": False,
                    "filter": None,
                    "sources": [{"id": 1, "key": "telegram-main"}],
                    "targets": [
                        {"endpoint": {"id": 2, "enabled": True}, "enabled": True, "transform": {}},
                        {"endpoint": {"id": 3, "enabled": True}, "enabled": True, "transform": {}},
                    ],
                }
            ],
        }

        endpoints, rules = compile_routes(config, "telegram-main")

        self.assertEqual({2, 3}, {endpoint["id"] for endpoint in endpoints})
        self.assertEqual(1, len(rules))
        self.assertTrue(rules[0]["continue"])
        self.assertEqual({"2", "3"}, {action["destination"] for action in rules[0]["actions"]})

    def test_route_for_another_source_is_not_loaded(self):
        config = {
            "endpoints": [],
            "routes": [{
                "key": "messenger-to-telegram",
                "name": "Messenger to Telegram",
                "enabled": True,
                "match_all_sources": False,
                "sources": [{"key": "messenger-main"}],
                "targets": [],
            }],
        }

        endpoints, rules = compile_routes(config, "telegram-main")

        self.assertEqual([], endpoints)
        self.assertEqual([], rules)


if __name__ == "__main__":
    unittest.main()

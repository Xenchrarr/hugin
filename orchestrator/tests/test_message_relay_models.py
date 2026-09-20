import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.models.orchestrator.MessageRelay import (
    MessageRelayEndpoint,
    MessageRelayRoute,
    MessageRelayTarget,
)


class MessageRelayModelTests(unittest.TestCase):
    def test_route_serializes_many_sources_and_targets(self):
        now = datetime(2026, 9, 18, tzinfo=timezone.utc)
        telegram = MessageRelayEndpoint(
            id=1,
            key="telegram-main",
            name="Telegram",
            type="telegram",
            capabilities=["source"],
        )
        phone = MessageRelayEndpoint(
            id=2,
            key="phone",
            name="Phone",
            type="sms",
            capabilities=["target"],
            config={"phone": "+4712345678"},
        )
        route = MessageRelayRoute(
            id=3,
            key="telegram-everywhere",
            name="Telegram everywhere",
            sources=[telegram],
            targets=[MessageRelayTarget(endpoint=phone)],
            created_at=now,
        )

        result = route.to_dict()

        self.assertEqual("telegram-main", result["sources"][0]["key"])
        self.assertNotIn("config", result["sources"][0])
        self.assertEqual("+4712345678", result["targets"][0]["endpoint"]["config"]["phone"])

    def test_write_model_collects_source_and_target_ids(self):
        route = MessageRelayRoute.from_dict({
            "id": 4,
            "key": "all-to-lora",
            "name": "Everything to LoRa",
            "match_all_sources": True,
            "source_endpoint_ids": [1, "2"],
            "targets": [{"endpoint_id": 9, "enabled": False}],
        })

        self.assertEqual([1, 2], route.source_endpoint_ids)
        self.assertEqual(9, route.target_specs[0]["endpoint_id"])


if __name__ == "__main__":
    unittest.main()

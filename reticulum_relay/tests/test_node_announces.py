import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.node import AnnounceRateLimitError, ReticulumNode


class _Site:
    destination_hash = "22" * 16

    def __init__(self):
        self.calls = 0

    def announce(self):
        self.calls += 1


class _Router:
    propagation_destination = SimpleNamespace(hash=bytes.fromhex("33" * 16))

    def __init__(self):
        self.delivery_announces = []
        self.propagation_announces = 0

    def announce(self, destination_hash):
        self.delivery_announces.append(destination_hash)

    def announce_propagation_node(self):
        self.propagation_announces += 1


class NodeAnnounceTests(unittest.TestCase):
    def test_announces_all_hugin_destinations_and_rate_limits_repeats(self):
        config = SimpleNamespace(propagation_enabled=True)
        node = ReticulumNode(config, Mock(), Mock())
        node._ready = True
        node._router = _Router()
        node._delivery_destination = SimpleNamespace(hash=bytes.fromhex("11" * 16))
        node._site = _Site()

        with patch("app.node.time.monotonic", return_value=100), patch(
            "app.node.time.time", return_value=123
        ):
            result = node.announce("all")
            with self.assertRaises(AnnounceRateLimitError):
                node.announce("delivery")

        self.assertEqual(["delivery", "site", "propagation"], [
            item["target"] for item in result["targets"]
        ])
        self.assertEqual(1, len(node._router.delivery_announces))
        self.assertEqual(1, node._site.calls)
        self.assertEqual(1, node._router.propagation_announces)

    def test_rejects_propagation_announce_when_disabled(self):
        node = ReticulumNode(SimpleNamespace(propagation_enabled=False), Mock(), Mock())
        node._ready = True
        node._router = _Router()
        node._delivery_destination = SimpleNamespace(hash=bytes.fromhex("11" * 16))
        node._site = _Site()

        with self.assertRaisesRegex(ValueError, "not enabled"):
            node.announce("propagation")


if __name__ == "__main__":
    unittest.main()

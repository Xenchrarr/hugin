import unittest

from src.commands.relay import list as relay_list_module
from src.commands.relay import toggle as relay_toggle_module
from src.commands.relay.list import RelayListCommand
from src.commands.relay.toggle import RelayStartCommand, RelayStopCommand
from src import command_processor as command_processor_module
from src.command_processor import CommandProcessor
from src.models.parsed_command import ParsedCommand


def _route(key="telegram-sms", enabled=False, target_type="sms"):
    return {
        "id": 1,
        "key": key,
        "name": "Telegram to SMS",
        "enabled": enabled,
        "targets": [
            {
                "enabled": True,
                "endpoint": {"key": "phone", "name": "Dumbphone", "type": target_type},
            }
        ],
    }


class _FakeOrchestrator:
    def __init__(self, routes):
        self.routes = routes
        self.updates = []

    def get_message_routes(self):
        return self.routes

    def lookup_user(self, channel, identifier):
        return {"id": 1, "is_admin": True, "config": {}}

    def set_message_route_enabled(self, key, enabled):
        self.updates.append((key, enabled))
        return {"key": key, "enabled": enabled, "runtime_applied": True}


class RelayRouteCommandTests(unittest.TestCase):
    def setUp(self):
        self.original_toggle = relay_toggle_module._orchestrator
        self.original_list = relay_list_module._orchestrator
        self.original_processor = command_processor_module._orchestrator

    def tearDown(self):
        relay_toggle_module._orchestrator = self.original_toggle
        relay_list_module._orchestrator = self.original_list
        command_processor_module._orchestrator = self.original_processor

    def test_relay_on_without_name_selects_the_only_sms_route(self):
        fake = _FakeOrchestrator([_route()])
        relay_toggle_module._orchestrator = fake

        result = RelayStartCommand().execute(ParsedCommand(path="relay/on"))

        self.assertEqual([("telegram-sms", True)], fake.updates)
        self.assertIn("on", result)

    def test_unnamed_toggle_is_rejected_when_sms_route_is_ambiguous(self):
        fake = _FakeOrchestrator([_route("first"), _route("second")])
        relay_toggle_module._orchestrator = fake

        result = RelayStopCommand().execute(ParsedCommand(path="relay/off"))

        self.assertEqual([], fake.updates)
        self.assertIn("More than one route", result)

    def test_relay_on_uses_toggle_handler_in_command_processor(self):
        fake = _FakeOrchestrator([_route()])
        relay_toggle_module._orchestrator = fake
        relay_list_module._orchestrator = fake
        command_processor_module._orchestrator = fake

        result = CommandProcessor().process("relay on", sender="+4712345678")

        self.assertEqual([("telegram-sms", True)], fake.updates)
        self.assertIn("on", result)

    def test_list_shows_target_state(self):
        route = _route(enabled=True)
        route["targets"][0]["enabled"] = False
        relay_list_module._orchestrator = _FakeOrchestrator([route])

        result = RelayListCommand().execute(ParsedCommand(path="relay"))

        self.assertIn("[ON] Telegram to SMS", result)
        self.assertIn("Dumbphone (off)", result)


if __name__ == "__main__":
    unittest.main()

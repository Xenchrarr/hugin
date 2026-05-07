from __future__ import annotations

from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class RelayPresetOnCommand(BaseCommand):
    path = "relay/preset/on"
    aliases = ["relay/preset on"]
    description = "Enable all preset Telegram relay rules"
    usage = "relay/preset/on"
    requires_pin = True

    def execute(self, cmd: ParsedCommand) -> str:
        result = _orchestrator.set_relay_preset(enabled=True)
        if result is None:
            return error_response(ERR_INTERNAL, "Failed to enable preset rules")
        return "Preset ON: all preset relay rules enabled."


class RelayPresetOffCommand(BaseCommand):
    path = "relay/preset/off"
    aliases = ["relay/preset off"]
    description = "Disable all preset Telegram relay rules"
    usage = "relay/preset/off"
    requires_pin = True

    def execute(self, cmd: ParsedCommand) -> str:
        result = _orchestrator.set_relay_preset(enabled=False)
        if result is None:
            return error_response(ERR_INTERNAL, "Failed to disable preset rules")
        return "Preset OFF: all preset relay rules disabled."

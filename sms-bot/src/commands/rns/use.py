from src.api.reticulum_relay import ReticulumRelayClient
from src.commands.base_command import BaseCommand
from src.commands.rns.send import RnsSendCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = ReticulumRelayClient()


class RnsUseCommand(BaseCommand):
    path = "rns/use"
    aliases = ["rns/target"]
    description = "Select the Reticulum conversation used by rns/reply"
    usage = "rns/use <num|destination_hash>"

    def execute(self, cmd: ParsedCommand) -> str:
        if len(cmd.positional) != 1:
            return error_response(ERR_BAD_ARG, "Usage: rns/use <num>", self.usage)
        if not cmd.sender_phone:
            return error_response(ERR_INTERNAL, "Cannot determine sender phone")
        resolved = RnsSendCommand._resolve_destination(cmd.positional[0])
        if resolved is None:
            return error_response(ERR_BAD_ARG, "Unknown Reticulum conversation", "Use rns/list")
        destination_hash, name = resolved
        if not _relay.set_context(cmd.sender_phone, destination_hash):
            return error_response(ERR_INTERNAL, "Failed to save Reticulum target")
        return f"Using: {name}"


from src.api.reticulum_relay import ReticulumRelayClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = ReticulumRelayClient()


class RnsReplyCommand(BaseCommand):
    path = "rns/reply"
    aliases = ["rns/r"]
    description = "Reply to the active Reticulum conversation"
    usage = "rns/reply <message>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return error_response(ERR_BAD_ARG, "Usage: rns/reply <message>", self.usage)
        if not cmd.sender_phone:
            return error_response(ERR_INTERNAL, "Cannot determine sender phone")
        context = _relay.get_context(cmd.sender_phone)
        if context is None:
            return error_response(
                ERR_BAD_ARG, "No active Reticulum conversation", "Use rns/use <num>"
            )
        destination_hash = str(context["destination_hash"])
        if not _relay.send_message(destination_hash, " ".join(cmd.positional)):
            return error_response(ERR_INTERNAL, "Failed to send Reticulum message")
        return f"OK sent to {context.get('display_name') or destination_hash[:12]}"


from src.api.messenger_relay import MessengerRelayClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = MessengerRelayClient()


class FbReplyCommand(BaseCommand):
    path = "fb/reply"
    aliases = ["fb/r"]
    description = "Reply to the active Messenger conversation"
    usage = "fb/reply <message>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return error_response(ERR_BAD_ARG, "Usage: fb/reply <message>", self.usage)
        if not cmd.sender_phone:
            return error_response(ERR_INTERNAL, "Cannot determine sender phone")
        context = _relay.get_context(cmd.sender_phone)
        if context is None:
            return error_response(ERR_BAD_ARG, "No active Messenger conversation", "Use fb/use <num>")
        if not _relay.send_message(str(context["thread_id"]), " ".join(cmd.positional)):
            return error_response(ERR_INTERNAL, "Failed to send Messenger message")
        return f"OK sent to {context.get('title') or context['thread_id']}"

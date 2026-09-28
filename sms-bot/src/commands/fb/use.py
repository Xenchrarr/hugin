from src.api.messenger_relay import MessengerRelayClient
from src.commands.base_command import BaseCommand
from src.commands.fb.send import FbSendCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = MessengerRelayClient()


class FbUseCommand(BaseCommand):
    path = "fb/use"
    aliases = ["fb/target"]
    description = "Select the Messenger conversation used by fb/reply"
    usage = "fb/use <num|thread_id>"

    def execute(self, cmd: ParsedCommand) -> str:
        if len(cmd.positional) != 1:
            return error_response(ERR_BAD_ARG, "Usage: fb/use <num>", self.usage)
        if not cmd.sender_phone:
            return error_response(ERR_INTERNAL, "Cannot determine sender phone")
        resolved = FbSendCommand._resolve_thread(cmd.positional[0])
        if resolved is None:
            return error_response(ERR_BAD_ARG, "Unknown Messenger conversation", "Use fb/list")
        thread_id, title = resolved
        if not _relay.set_context(cmd.sender_phone, thread_id):
            return error_response(ERR_INTERNAL, "Failed to save Messenger target")
        return f"Using: {title}"

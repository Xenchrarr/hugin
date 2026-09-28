from src.api.messenger_relay import MessengerRelayClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = MessengerRelayClient()


class FbSendCommand(BaseCommand):
    path = "fb/send"
    aliases = []
    description = "Send a message to a Messenger conversation"
    usage = "fb/send <num|thread_id> <message>"

    def execute(self, cmd: ParsedCommand) -> str:
        if len(cmd.positional) < 2:
            return error_response(ERR_BAD_ARG, "Usage: fb/send <num> <message>", self.usage)
        resolved = self._resolve_thread(cmd.positional[0])
        if resolved is None:
            return error_response(
                ERR_BAD_ARG,
                f"Could not resolve conversation '{cmd.positional[0]}'",
                "Use fb/list to see available conversations",
            )
        thread_id, title = resolved
        if not _relay.send_message(thread_id, " ".join(cmd.positional[1:])):
            return error_response(ERR_INTERNAL, "Failed to send Messenger message")
        if cmd.sender_phone:
            _relay.set_context(cmd.sender_phone, thread_id)
        return f"Sent: {title}"

    @staticmethod
    def _resolve_thread(target: str) -> tuple[str, str] | None:
        conversations = _relay.get_conversations()
        if target.isdigit():
            index = int(target)
            if 1 <= index <= len(conversations):
                item = conversations[index - 1]
                return str(item["thread_id"]), item.get("title") or str(item["thread_id"])
            # Messenger thread IDs are numeric, so allow a raw ID too.
            return target, target
        return None

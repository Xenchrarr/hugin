from src.api.reticulum_relay import ReticulumRelayClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = ReticulumRelayClient()


class RnsSendCommand(BaseCommand):
    path = "rns/send"
    aliases = []
    description = "Send a message to a Reticulum conversation"
    usage = "rns/send <num|destination_hash> <message>"

    def execute(self, cmd: ParsedCommand) -> str:
        if len(cmd.positional) < 2:
            return error_response(ERR_BAD_ARG, "Usage: rns/send <num> <message>", self.usage)
        resolved = self._resolve_destination(cmd.positional[0])
        if resolved is None:
            return error_response(
                ERR_BAD_ARG,
                "Unknown Reticulum conversation or destination hash",
                "Use rns/list or supply a 32-character hash",
            )
        destination_hash, name = resolved
        if not _relay.send_message(destination_hash, " ".join(cmd.positional[1:])):
            return error_response(ERR_INTERNAL, "Failed to send Reticulum message")
        if cmd.sender_phone:
            _relay.set_context(cmd.sender_phone, destination_hash)
        return f"Sent: {name}"

    @staticmethod
    def _resolve_destination(target: str) -> tuple[str, str] | None:
        conversations = _relay.get_conversations()
        if target.isdigit():
            index = int(target)
            if 1 <= index <= len(conversations):
                item = conversations[index - 1]
                destination_hash = str(item["destination_hash"])
                return destination_hash, item.get("display_name") or destination_hash[:12]
        normalized = target.strip().lower()
        if len(normalized) == 32:
            try:
                bytes.fromhex(normalized)
                return normalized, normalized[:12]
            except ValueError:
                return None
        return None


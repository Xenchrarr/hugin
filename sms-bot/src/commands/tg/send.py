from src.api.telegram_relay import TelegramRelayClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = TelegramRelayClient()


class TgSendCommand(BaseCommand):
    path = "tg/send"
    aliases = []
    description = "Send a message to a Telegram conversation"
    usage = "tg/send <num|chat_id> <message>"
    requires_pin = True

    def execute(self, cmd: ParsedCommand) -> str:
        if len(cmd.positional) < 2:
            return error_response(ERR_BAD_ARG, "Usage: tg/send <num> <message>", self.usage)

        target = cmd.positional[0]
        text = " ".join(cmd.positional[1:])

        chat_id = self._resolve_chat(target)
        if chat_id is None:
            return error_response(ERR_BAD_ARG, f"Could not resolve conversation '{target}'",
                                  "Use tg/list to see available conversations")

        ok = _relay.send_message(chat_id, text)
        if not ok:
            return error_response(ERR_INTERNAL, "Failed to send Telegram message")

        # Update sticky reply context for this sender so tg/reply works immediately
        if cmd.sender_phone:
            _relay.set_context(cmd.sender_phone, chat_id)

        return f"OK sent to chat {chat_id}"

    @staticmethod
    def _resolve_chat(target: str) -> int | None:
        """Resolve conversation by 1-based index (from tg/list) or raw chat_id."""
        convos = _relay.get_conversations()
        # Try numeric index first
        if target.lstrip("-").isdigit():
            num = int(target)
            # 1-based index into the current conversation list
            if 1 <= num <= len(convos):
                return convos[num - 1]["chat_id"]
            # Otherwise treat as a raw chat_id
            return num
        return None

from src.api.telegram_relay import TelegramRelayClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = TelegramRelayClient()


class TgReplyCommand(BaseCommand):
    path = "tg/reply"
    aliases = ["tg/r"]
    description = "Reply to the last active Telegram conversation"
    usage = "tg/reply <message>"
    requires_pin = True

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return error_response(ERR_BAD_ARG, "Usage: tg/reply <message>", self.usage)

        if not cmd.sender_phone:
            return error_response(ERR_INTERNAL, "Cannot determine sender phone for context lookup")

        ctx = _relay.get_context(cmd.sender_phone)
        if ctx is None:
            return error_response(
                ERR_BAD_ARG,
                "No active Telegram conversation",
                "Use tg/send <num> <msg> to start one",
            )

        text = " ".join(cmd.positional)
        ok = _relay.send_message(ctx["chat_id"], text)
        if not ok:
            return error_response(ERR_INTERNAL, "Failed to send Telegram message")

        title = ctx.get("title") or str(ctx["chat_id"])
        return f"OK sent to {title}"

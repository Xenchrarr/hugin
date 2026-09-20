from src.api.telegram_relay import TelegramRelayClient
from src.commands.base_command import BaseCommand
from src.commands.tg.send import TgSendCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_relay = TelegramRelayClient()


class TgUseCommand(BaseCommand):
    path = "tg/use"
    aliases = ["tg/target"]
    description = "Select the Telegram conversation used by tg/reply and unaddressed media"
    usage = "tg/use <num|chat_id>"

    def execute(self, cmd: ParsedCommand) -> str:
        if len(cmd.positional) != 1:
            return error_response(ERR_BAD_ARG, "Usage: tg/use <num>", self.usage)
        if not cmd.sender_phone:
            return error_response(ERR_INTERNAL, "Cannot determine sender phone")

        resolved = TgSendCommand._resolve_chat(cmd.positional[0])
        if resolved is None:
            return error_response(
                ERR_BAD_ARG,
                f"Could not resolve conversation '{cmd.positional[0]}'",
                "Use tg/list to see available conversations",
            )

        chat_id, title = resolved
        if not _relay.set_context(cmd.sender_phone, chat_id):
            return error_response(ERR_INTERNAL, "Failed to save Telegram target")
        return f"Using: {title}"

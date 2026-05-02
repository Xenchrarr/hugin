import re

from src.api.telegram_relay import TelegramRelayClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand


def _gsm_safe(s: str) -> str:
    """Strip characters outside Latin-1 (emoji, CJK, etc.) that break GSM text mode."""
    return re.sub(r"[^\x00-\xFF]", "", s)

_relay = TelegramRelayClient()


class TgListCommand(BaseCommand):
    path = "tg/list"
    aliases = ["tg/convos"]
    description = "List recent Telegram conversations"
    usage = "tg/list"

    def execute(self, cmd: ParsedCommand) -> str:
        convos = _relay.get_conversations()
        if not convos:
            return "No recent Telegram conversations."
        lines = []
        for c in convos:
            sender = c.get("last_sender") or "?"
            snippet = c.get("last_text") or ""
            title = _gsm_safe(c.get("title") or str(c.get("chat_id")))
            lines.append(f"{c['index']}. {title}")
        return "\n".join(lines)

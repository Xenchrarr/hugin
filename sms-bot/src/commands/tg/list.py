import re

from src.api.telegram_relay import TelegramRelayClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand


def _gsm_safe(s: str) -> str:
    """Strip characters outside Latin-1 (emoji, CJK, etc.) that break GSM text mode."""
    return re.sub(r"[^\x00-\xFF]", "", s)


_MAX_CONVERSATIONS = 10
# Norwegian letters are part of GSM-7, so the complete menu can use the long
# single-part format after reserving the modem's trailing workaround character.
_MENU_MAX_LENGTH = 159
_LIST_OVERHEAD = sum(len(f"{i}. ") for i in range(1, _MAX_CONVERSATIONS + 1)) + (
    _MAX_CONVERSATIONS - 1
)
_MAX_TITLE_LENGTH = (
    _MENU_MAX_LENGTH - _LIST_OVERHEAD
) // _MAX_CONVERSATIONS


def _shorten_title(title: str) -> str:
    if len(title) <= _MAX_TITLE_LENGTH:
        return title
    return title[:_MAX_TITLE_LENGTH - 1] + ">"


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
        for c in convos[:_MAX_CONVERSATIONS]:
            title = _gsm_safe(c.get("title") or str(c.get("chat_id")))
            lines.append(f"{c['index']}. {_shorten_title(title)}")
        return "\n".join(lines)

import re

from src.api.messenger_relay import MessengerRelayClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_relay = MessengerRelayClient()


def _safe_title(value: str) -> str:
    value = re.sub(r"[^\x00-\xFF]", "", value)
    return value if len(value) <= 12 else value[:11] + ">"


class FbListCommand(BaseCommand):
    path = "fb/list"
    aliases = ["fb/convos"]
    description = "List recent Messenger conversations"
    usage = "fb/list"

    def execute(self, cmd: ParsedCommand) -> str:
        conversations = _relay.get_conversations()
        if not conversations:
            return "No recent Messenger conversations."
        return "\n".join(
            f"{item['index']}. {_safe_title(item.get('title') or item['thread_id'])}"
            for item in conversations[:10]
        )

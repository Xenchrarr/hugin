import re

from src.api.reticulum_relay import ReticulumRelayClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_relay = ReticulumRelayClient()


def _short(value: str) -> str:
    value = re.sub(r"[^\x00-\xFF]", "", value)
    return value if len(value) <= 12 else value[:11] + ">"


class RnsListCommand(BaseCommand):
    path = "rns/list"
    aliases = ["rns/convos"]
    description = "List recent Reticulum conversations"
    usage = "rns/list"

    def execute(self, cmd: ParsedCommand) -> str:
        conversations = _relay.get_conversations()
        if not conversations:
            return "No recent Reticulum conversations."
        return "\n".join(
            f"{item['index']}. {_short(item.get('display_name') or item['destination_hash'][:12])}"
            for item in conversations[:10]
        )


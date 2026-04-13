from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.parsed_command import ParsedCommand


class BaseCommand:
    path: str = ""
    aliases: list[str] = []
    description: str = ""
    usage: str = ""
    requires_pin: bool = False

    def execute(self, cmd: ParsedCommand) -> str:
        raise NotImplementedError
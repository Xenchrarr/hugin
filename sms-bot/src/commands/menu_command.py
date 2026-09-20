from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand


class MenuCommand(BaseCommand):
    path = "menu"
    aliases = ["m"]
    description = "Show the dumb-phone shortcut menu"
    usage = "menu"

    def execute(self, cmd: ParsedCommand) -> str:
        return (
            "1 Today  2 Shopping  3 Home\n"
            "4 Messages  5 Notes  6 Help\n"
            "Quick: t <time> <text>, r <text>, cam"
        )

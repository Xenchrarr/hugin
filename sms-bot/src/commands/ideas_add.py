from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.services.ideas_service import add_to_ideas


class IdeasAddCommand(BaseCommand):
    path = "ideas/add"
    aliases = ["idea/add"]
    description = "Add item to ideas note"
    usage = "ideas add <idea>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing idea. Hint: ideas add build a treehouse"
        item = " ".join(cmd.positional)
        add_to_ideas(item)
        return f"OK added idea: {item}"

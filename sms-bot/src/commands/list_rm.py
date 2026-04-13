from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.services.simple_note_service import remove_from_shopping_list


class ListRmCommand(BaseCommand):
    path = "list/rm"
    aliases = []
    description = "Remove item from shopping list"
    usage = "list rm <item>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing item. Hint: list rm milk"
        item = " ".join(cmd.positional)
        removed = remove_from_shopping_list(item)
        if removed:
            return f"OK removed: {item}"
        return f"ERR_BAD_ARG: '{item}' not found in list"

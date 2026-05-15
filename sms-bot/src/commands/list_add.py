from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.services.simple_note_service import add_to_shopping_list


class ListAddCommand(BaseCommand):
    path = "list/add"
    aliases = []
    description = "Add item to shopping list"
    usage = "list add <item>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing item. Hint: list add milk"
        item = " ".join(cmd.positional)
        added = add_to_shopping_list(item)
        if added:
            return f"{item} added"
        return "ERR_INTERNAL: Failed to add item"

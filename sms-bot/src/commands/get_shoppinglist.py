from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.services.simple_note_service import get_shopping_list


class GetShoppingListCommand(BaseCommand):
    path = "list/show"
    aliases = ["get/shoppinglist"]
    description = "Show the shopping list"
    usage = "list show"

    def execute(self, cmd: ParsedCommand) -> str:
        return get_shopping_list()
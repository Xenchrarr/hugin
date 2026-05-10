from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.api.printer import print_shopping_list


class ListPrintCommand(BaseCommand):
    path = "list/print"
    aliases = ["print/list"]
    description = "Print the shopping list on the thermal printer"
    usage = "list print"

    def execute(self, cmd: ParsedCommand) -> str:
        ok = print_shopping_list()
        if ok:
            return "OK: Shopping list sent to printer"
        return "ERR: Failed to print shopping list"

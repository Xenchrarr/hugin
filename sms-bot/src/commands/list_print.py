from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
import os

from src.api.core import HuginCoreClient
from src.api.printer import print_content

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


class ListPrintCommand(BaseCommand):
    path = "list/print"
    aliases = ["print/list"]
    description = "Print the shopping list on the thermal printer"
    usage = "list print"

    def execute(self, cmd: ParsedCommand) -> str:
        content = _core.get_shopping_list()
        if content is None:
            return "ERR: Could not fetch shopping list"
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        ok = bool(lines) and print_content(lines, title="SHOPPING")
        if ok:
            return "OK: Shopping list sent to printer"
        return "ERR: Failed to print shopping list"

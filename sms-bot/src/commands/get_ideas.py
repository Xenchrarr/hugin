from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.services.ideas_service import get_ideas


class GetIdeasCommand(BaseCommand):
    path = "ideas/show"
    aliases = ["ideas/list"]
    description = "Show ideas note"
    usage = "ideas show"

    def execute(self, cmd: ParsedCommand) -> str:
        return get_ideas()

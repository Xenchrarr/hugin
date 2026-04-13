import dateparser

from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand


class RemindCommand(BaseCommand):
    path = "rem/in"
    aliases = ["remind"]
    description = "Set a reminder (stub)"
    usage = "rem in <duration> <message>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing duration. Hint: rem in 45m check oven"

        time_string = cmd.positional[0]
        message = " ".join(cmd.positional[1:]) or "Reminder"

        parsed_time = dateparser.parse(time_string)
        if not parsed_time:
            return f"ERR_BAD_ARG: Could not parse time '{time_string}'. Hint: rem in 45m check oven"

        return f"OK rem set for {parsed_time.strftime('%Y-%m-%d %H:%M')}: {message}"
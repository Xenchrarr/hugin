import dateparser

from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class RemindCommand(BaseCommand):
    path = "rem/in"
    aliases = ["remind"]
    description = "Set a reminder"
    usage = "rem in <duration> <message>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing duration. Hint: rem in 45m check oven"

        time_string = cmd.positional[0]
        message = " ".join(cmd.positional[1:]) or "Reminder"

        parsed_time = dateparser.parse(time_string)
        if not parsed_time:
            return f"ERR_BAD_ARG: Could not parse time '{time_string}'. Hint: rem in 45m check oven"

        recurrence = cmd.named.get("repeat") or cmd.named.get("recurrence")

        result = _orchestrator.create_reminder(
            title=message,
            due_at=parsed_time.isoformat(),
            recurrence=recurrence,
            created_by="sms",
        )

        if result is None:
            return "ERR_INTERNAL: Failed to create reminder"

        rid = result.get("id", "?")
        return f"OK reminder #{rid} set for {parsed_time.strftime('%Y-%m-%d %H:%M')}: {message}"
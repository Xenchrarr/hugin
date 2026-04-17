from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class DismissCommand(BaseCommand):
    path = "rem/dismiss"
    aliases = ["dismiss"]
    description = "Dismiss a reminder"
    usage = "rem dismiss <id>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing reminder ID. Hint: dismiss 1"

        try:
            reminder_id = int(cmd.positional[0])
        except ValueError:
            return "ERR_BAD_ARG: Invalid reminder ID"

        result = _orchestrator.dismiss_reminder(reminder_id)
        if result is None:
            return "ERR_INTERNAL: Failed to dismiss reminder"

        return f"OK reminder #{reminder_id} dismissed"

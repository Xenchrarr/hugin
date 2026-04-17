from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class SnoozeCommand(BaseCommand):
    path = "rem/snooze"
    aliases = ["snooze"]
    description = "Snooze a reminder"
    usage = "rem snooze <id> [duration]"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing reminder ID. Hint: snooze 1 10m"

        try:
            reminder_id = int(cmd.positional[0])
        except ValueError:
            return "ERR_BAD_ARG: Invalid reminder ID"

        duration = cmd.positional[1] if len(cmd.positional) > 1 else "10m"

        result = _orchestrator.snooze_reminder(reminder_id, duration)
        if result is None:
            return "ERR_INTERNAL: Failed to snooze reminder"

        due = result.get("due_at", "?")
        if isinstance(due, str) and "T" in due:
            due = due[:16].replace("T", " ")

        return f"OK reminder #{reminder_id} snoozed until {due}"

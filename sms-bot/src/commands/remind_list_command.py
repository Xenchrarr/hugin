from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class RemindListCommand(BaseCommand):
    path = "rem/list"
    aliases = ["reminders"]
    description = "List active reminders"
    usage = "rem list"

    def execute(self, cmd: ParsedCommand) -> str:
        status = cmd.positional[0] if cmd.positional else "active"
        reminders = _orchestrator.list_reminders(status=status, user_id=cmd.user_id)

        if reminders is None:
            return "ERR_INTERNAL: Failed to fetch reminders"

        if not reminders:
            return f"OK no {status} reminders"

        lines = []
        for r in reminders[:10]:
            due = r.get("due_at", "?")
            if isinstance(due, str) and "T" in due:
                due = due[:16].replace("T", " ")
            lines.append(f"#{r['id']} {due} {r['title']}")

        return "OK reminders:\n" + "\n".join(lines)

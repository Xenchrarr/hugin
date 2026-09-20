from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.commands.brief_command import _parse_time
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class QuietCommand(BaseCommand):
    path = "quiet"
    aliases = []
    description = "Set quiet hours for proactive SMS messages"
    usage = "quiet <HHMM> <HHMM> | quiet off"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.user_id:
            return "Could not identify user"
        if cmd.positional and cmd.positional[0].lower() == "off":
            result = _orchestrator.patch_user_config(cmd.user_id, {"sms_quiet_hours": None})
            return "Quiet hours off" if result is not None else "Could not update quiet hours"
        if len(cmd.positional) != 2:
            return "Usage: quiet 2200 0700 | quiet off"
        start = _parse_time(cmd.positional[0])
        end = _parse_time(cmd.positional[1])
        if not start or not end:
            return "Use times like: quiet 2200 0700"
        result = _orchestrator.patch_user_config(cmd.user_id, {
            "sms_quiet_hours": {"start": start, "end": end},
        })
        return f"Quiet {start}-{end}" if result is not None else "Could not update quiet hours"

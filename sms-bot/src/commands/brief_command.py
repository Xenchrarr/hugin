import re

from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


def _parse_time(value: str) -> str | None:
    compact = re.sub(r"[^0-9]", "", value)
    if len(compact) == 3:
        compact = "0" + compact
    if len(compact) != 4:
        return None
    hour, minute = int(compact[:2]), int(compact[2:])
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


class BriefCommand(BaseCommand):
    path = "brief"
    aliases = []
    description = "Schedule a compact daily briefing"
    usage = "brief <HHMM|off>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.user_id or not cmd.sender_phone:
            return "Could not identify user"
        if not cmd.positional:
            return "Usage: brief 0730 | brief off"
        value = cmd.positional[0].lower()
        if value == "off":
            return "Brief off" if _orchestrator.configure_brief(cmd.user_id, cmd.sender_phone, None) else "Could not disable brief"
        parsed = _parse_time(value)
        if parsed is None:
            return "Use a time like 0730 or 07:30"
        ok = _orchestrator.configure_brief(cmd.user_id, cmd.sender_phone, parsed)
        return f"Daily brief set for {parsed}" if ok else "Could not schedule brief"

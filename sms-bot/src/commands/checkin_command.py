from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class CheckinCommand(BaseCommand):
    path = "checkin"
    aliases = ["check"]
    description = "Start a safety check-in deadline"
    usage = "checkin <minutes>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.user_id or not cmd.sender_phone:
            return "Could not identify user"
        if not cmd.positional:
            return "Usage: checkin 30"
        raw = cmd.positional[0].lower().removesuffix("m")
        if not raw.isdigit():
            return "Use minutes, for example: checkin 30"
        minutes = max(1, min(int(raw), 24 * 60))
        if not cmd.user_config.get("checkin_alert_phone"):
            return "Set config.checkin_alert_phone before using check-in."
        result = _orchestrator.create_checkin(cmd.user_id, cmd.sender_phone, minutes)
        if result is None:
            return "Could not start check-in"
        return f"Check-in #{result.get('id')} active for {minutes}m. Reply OK to confirm safety."


class CheckinOkCommand(BaseCommand):
    path = "ok"
    aliases = ["safe"]
    description = "Acknowledge the active safety check-in"
    usage = "ok"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.user_id:
            return "Could not identify user"
        result = _orchestrator.acknowledge_checkin(cmd.user_id)
        if result is None:
            return "No active check-in"
        return "Check-in confirmed."

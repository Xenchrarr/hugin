import dateparser
from zoneinfo import ZoneInfo

from src.api.orchestrator import OrchestratorClient

_TZ = ZoneInfo("Europe/Oslo")
_DATEPARSER_SETTINGS = {
    'PREFER_DATES_FROM': 'future',
    'TIMEZONE': 'Europe/Oslo',
    'RETURN_AS_TIMEZONE_AWARE': True,
}
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

        _TIME_UNITS = {
            "min", "mins", "minute", "minutes",
            "hour", "hours", "hr", "hrs",
            "sec", "secs", "second", "seconds",
            "day", "days", "week", "weeks",
        }
        time_string = cmd.positional[0]
        msg_start = 1
        # If the AI gave a bare number, consume the next token if it's a time unit
        if time_string.isdigit() and len(cmd.positional) > 1 and cmd.positional[1].lower() in _TIME_UNITS:
            time_string = f"{time_string} {cmd.positional[1]}"
            msg_start = 2
        message = " ".join(cmd.positional[msg_start:]) or "Reminder"

        parsed_time = dateparser.parse(time_string, settings=_DATEPARSER_SETTINGS)
        if not parsed_time:
            return f"ERR_BAD_ARG: Could not parse time '{time_string}'. Hint: rem in 45m check oven"

        recurrence = cmd.named.get("repeat") or cmd.named.get("recurrence")

        result = _orchestrator.create_reminder(
            title=message,
            due_at=parsed_time.isoformat(),
            recurrence=recurrence,
            user_id=cmd.user_id,
            created_by="sms",
        )

        if result is None:
            return "ERR_INTERNAL: Failed to create reminder"

        rid = result.get("id", "?")
        display_time = parsed_time.astimezone(_TZ).strftime('%Y-%m-%d %H:%M')
        return f"Reminder #{rid}: {display_time}"
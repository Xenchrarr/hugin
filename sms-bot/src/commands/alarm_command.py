from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import dateparser

from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_api = OrchestratorClient()
_TZ = ZoneInfo("Europe/Oslo")


class AlarmCommand(BaseCommand):
    path = "alarm"
    aliases = ["wake"]
    description = "Create and manage calling alarms"
    usage = "alarm <time>|list|on|off|test|snooze"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "Usage: alarm 07:00 [label] repeat=daily|weekdays"
        action = cmd.positional[0].lower()
        if action == "list":
            alarms = _api.list_alarms(cmd.user_id)
            if alarms is None:
                return "ERR_INTERNAL: Could not list alarms"
            mine = [a for a in alarms if a.get("user_id") == cmd.user_id]
            return "No alarms" if not mine else "\n".join(
                f"#{a['id']} {'ON' if a['enabled'] else 'OFF'} {a['label']} {a.get('local_time') or a.get('scheduled_at')}"
                for a in mine[:10]
            )
        if action in {"on", "off", "test", "snooze"}:
            if len(cmd.positional) < 2 or not cmd.positional[1].isdigit():
                return f"Usage: alarm {action} <id>"
            alarm_id = int(cmd.positional[1])
            mapped = {"on": "enable", "off": "disable"}.get(action, action)
            values = {"minutes": int(cmd.positional[2].rstrip("m"))} if action == "snooze" and len(cmd.positional) > 2 else {}
            return f"Alarm #{alarm_id} {action}" if _api.alarm_action(cmd.user_id, alarm_id, mapped, **values) else "ERR_INTERNAL: Alarm action failed"

        repeat = (cmd.named.get("repeat") or "once").lower()
        label_start = 1
        if action == "in" and len(cmd.positional) > 1:
            parsed = dateparser.parse("in " + cmd.positional[1], settings={"TIMEZONE": "Europe/Oslo", "RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"})
            label_start = 2
        else:
            parsed = dateparser.parse(action, settings={"TIMEZONE": "Europe/Oslo", "RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"})
        if not parsed:
            return "ERR_BAD_ARG: Could not parse alarm time"
        label = " ".join(cmd.positional[label_start:]) or "Wake up"
        if repeat in {"daily", "weekdays"}:
            payload = {"schedule_type": repeat, "local_time": parsed.astimezone(_TZ).strftime("%H:%M")}
            if repeat == "weekdays":
                payload["weekdays"] = [0, 1, 2, 3, 4]
        else:
            payload = {"schedule_type": "once", "scheduled_at": parsed.isoformat()}
        result = _api.create_alarm(cmd.user_id, label, **payload)
        return f"Alarm #{result['id']} set" if result else "ERR_INTERNAL: Could not create alarm"


class CallMeCommand(BaseCommand):
    path = "call"
    aliases = ["ring"]
    description = "Call your registered phone now"
    usage = "call me"

    def execute(self, cmd: ParsedCommand) -> str:
        return "Calling now" if _api.call_user(cmd.user_id) else "ERR_INTERNAL: Call failed"

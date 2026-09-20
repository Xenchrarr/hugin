from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os

from src.api.core import HuginCoreClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))
_TZ = ZoneInfo("Europe/Oslo")


def _time(value: str) -> str:
    if not value or "T" not in value:
        return "all day"
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(_TZ).strftime("%H:%M")
    except (TypeError, ValueError):
        return "?"


def format_today(data: dict, weather: str = "", power: str = "") -> str:
    events = data.get("events") or []
    reminders = data.get("reminders") or []
    date_text = data.get("date", "Today")
    try:
        date_text = datetime.fromisoformat(date_text).strftime("%a %d")
    except (TypeError, ValueError):
        pass

    lines = [str(date_text)]
    if events:
        lines.append("Cal: " + "; ".join(
            f"{_time(event.get('start', ''))} {event.get('summary', '(untitled)')}"
            for event in events
        ))
    else:
        lines.append("Cal: clear")
    if reminders:
        lines.append("Rem: " + "; ".join(
            f"{_time(item.get('due_at', ''))} {item.get('title', 'Reminder')}"
            for item in reminders
        ))
    if weather:
        lines.append("Wx: " + weather.replace("Now: ", "", 1))
    if power:
        lines.append("Power: " + power)
    return "\n".join(lines)


class TodayCommand(BaseCommand):
    path = "today"
    aliases = ["day"]
    description = "Today's calendar, reminders, weather and solar"
    usage = "today"

    def execute(self, cmd: ParsedCommand) -> str:
        data = _core.get_today()
        if data is None:
            return "Today data unavailable"

        location_id = cmd.user_config.get("weather_location_id", "")
        weather_data = _core.get_weather_summary(location_id) if location_id else None
        weather = weather_data.get("text", "") if weather_data else ""

        growatt = _core.get_growatt_data()
        power = ""
        if growatt:
            power = f"{growatt.get('currentPower', '?')}W, {growatt.get('todayEnergy', '?')}kWh today"
        return format_today(data, weather, power)

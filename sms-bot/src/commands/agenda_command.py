import os
from collections import defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.api.core import HuginCoreClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))
_TZ = ZoneInfo("Europe/Oslo")

_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _parse_start(start_str: str) -> datetime | date | None:
    """Return a timezone-aware datetime or a date for all-day events."""
    if not start_str:
        return None
    try:
        if "T" in start_str:
            dt = datetime.fromisoformat(start_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(_TZ)
        # all-day: YYYY-MM-DD
        return date.fromisoformat(start_str)
    except ValueError:
        return None


def _format_time(start_str: str, all_day: bool) -> str:
    if all_day:
        return "All day"
    parsed = _parse_start(start_str)
    if isinstance(parsed, datetime):
        return parsed.strftime("%H:%M")
    return ""


def _event_date(start_str: str, all_day: bool) -> date | None:
    parsed = _parse_start(start_str)
    if isinstance(parsed, datetime):
        return parsed.date()
    if isinstance(parsed, date):
        return parsed
    return None


def _day_label(d: date) -> str:
    return f"{_DAY_ABBR[d.weekday()]} {d.day} {_MONTH_ABBR[d.month - 1]}"


def _calendar_tag(name: str, total_calendars: int) -> str:
    if total_calendars <= 1:
        return ""
    return f" [{name[:4]}]"


class AgendaCommand(BaseCommand):
    path = "agenda"
    aliases = ["cal"]
    description = "Show calendar events for the next week"
    usage = "agenda [days]"

    def execute(self, cmd: ParsedCommand) -> str:
        days = 7
        if cmd.positional:
            try:
                days = int(cmd.positional[0])
                days = max(1, min(days, 31))
            except ValueError:
                pass

        events = _core.get_agenda(days=days)
        if events is None:
            return "ERR_INTERNAL: Could not fetch calendar"
        if not events:
            return f"(no events in the next {days} day{'s' if days != 1 else ''})"

        n_cals = len({e.get("calendar_name", "") for e in events})

        grouped: dict[date, list[str]] = defaultdict(list)
        for event in events:
            start = event.get("start", "")
            all_day = event.get("all_day", False)
            d = _event_date(start, all_day)
            if d is None:
                continue
            time_str = _format_time(start, all_day)
            summary = event.get("summary", "(no title)")
            tag = _calendar_tag(event.get("calendar_name", ""), n_cals)
            grouped[d].append(f"{time_str} {summary}{tag}".strip())

        lines: list[str] = []
        for d in sorted(grouped):
            events_str = ", ".join(grouped[d])
            lines.append(f"{_day_label(d)}: {events_str}")

        return "\n".join(lines)

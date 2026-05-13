import textwrap
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from src.config import HUGIN_CORE_URL
from src.services.print_service import PrintService

PRINTER_WIDTH = 48
_TZ = ZoneInfo("Europe/Oslo")


class TodayService:
    def __init__(self):
        self.print_service = PrintService()

    def fetch_and_print(self) -> dict:
        url = f"{HUGIN_CORE_URL}/api/today/"
        response = requests.get(url, timeout=(5, 15))

        if response.status_code != 200:
            raise Exception(f"Failed to fetch today data: {response.status_code}")

        data = response.json()

        day_name = data.get("day_name", "").capitalize()
        today_str = data.get("date", "")
        month_name = data.get("month_name", "")
        day_num = self._day_number(today_str)

        title = f"I DAG -- {day_name} {day_num}. {month_name}"
        lines = self._format(data)
        now = datetime.now(_TZ).strftime("%H:%M")

        self.print_service.print_content(title=title, lines=lines, footer=f"Skrevet ut {now}")

        return {
            "status": "printed",
            "event_count": len(data.get("events", [])),
            "reminder_count": len(data.get("reminders", [])),
        }

    @staticmethod
    def _day_number(date_str: str) -> str:
        try:
            return str(datetime.fromisoformat(date_str).day)
        except (ValueError, TypeError):
            return date_str

    def _format(self, data: dict) -> list[str]:
        lines = []
        divider = "-" * PRINTER_WIDTH
        events = data.get("events", [])
        reminders = data.get("reminders", [])

        # --- Calendar ---
        lines.append("KALENDER")
        lines.append(divider)

        if not events:
            lines.append("  (ingen avtaler i dag)")
        else:
            for event in events:
                summary = event.get("summary", "(uten tittel)")
                cal = event.get("calendar_name", "")
                if event.get("all_day"):
                    label = f"* {summary}"
                else:
                    time_part = self._format_time(event.get("start", ""))
                    label = f"{time_part}  {summary}" if time_part else summary
                if cal:
                    label = f"{label} ({cal})"
                for wrapped in textwrap.wrap(label, width=PRINTER_WIDTH):
                    lines.append(wrapped)

        # --- Reminders (only if present) ---
        if reminders:
            lines.append("")
            lines.append("PAMINNELSER")
            lines.append(divider)
            for r in reminders:
                title = r.get("title", "(uten tittel)")
                time_part = self._format_time(r.get("due_at", ""))
                label = f"{time_part}  {title}" if time_part else title
                for wrapped in textwrap.wrap(label, width=PRINTER_WIDTH):
                    lines.append(wrapped)
                msg = r.get("message") or ""
                if msg:
                    for wrapped in textwrap.wrap(f"  {msg}", width=PRINTER_WIDTH)[:3]:
                        lines.append(wrapped)

        return lines

    @staticmethod
    def _format_time(dt_str: str) -> str:
        """Return HH:MM in Oslo timezone from an ISO-8601 string, or '' on failure."""
        if not dt_str or "T" not in dt_str:
            return ""
        try:
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(_TZ).strftime("%H:%M")
        except (ValueError, TypeError):
            return ""

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify

from src.api.orchestrator import ORCHESTRATOR_BASE_URL, session
from src.config import settings

log = logging.getLogger(__name__)

today_blueprint = Blueprint("today", __name__)

_TZ = ZoneInfo("Europe/Oslo")

_DAY_NAMES = {
    0: "mandag", 1: "tirsdag", 2: "onsdag",
    3: "torsdag", 4: "fredag", 5: "lørdag", 6: "søndag",
}

_MONTH_NAMES = {
    1: "januar", 2: "februar", 3: "mars", 4: "april",
    5: "mai", 6: "juni", 7: "juli", 8: "august",
    9: "september", 10: "oktober", 11: "november", 12: "desember",
}


def _today_oslo() -> date:
    return datetime.now(_TZ).date()


def _parse_event_date(start_str: str) -> date | None:
    """Return the date portion of an event start string in Europe/Oslo timezone."""
    try:
        if "T" in start_str:
            dt = datetime.fromisoformat(start_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(_TZ).date()
        else:
            return date.fromisoformat(start_str)
    except (ValueError, TypeError):
        return None


@today_blueprint.route("/")
def get_today():
    today = _today_oslo()

    # --- Calendar events ---
    all_events = []
    if ORCHESTRATOR_BASE_URL:
        try:
            resp = session.get(
                f"{ORCHESTRATOR_BASE_URL}/ical_sources/agenda",
                params={"days": 2},
                headers={"X-Service-Key": settings.SERVICE_KEY},
                timeout=15,
            )
            resp.raise_for_status()
            all_events = resp.json().get("events", [])
        except Exception:
            log.exception("Failed to fetch calendar events from orchestrator")

    events = [e for e in all_events if _parse_event_date(e["start"]) == today]

    # --- Reminders from orchestrator (optional) ---
    reminders = []
    if ORCHESTRATOR_BASE_URL:
        try:
            resp = session.get(
                f"{ORCHESTRATOR_BASE_URL}/reminders/list",
                params={"status": "active"},
                timeout=5,
            )
            resp.raise_for_status()
            all_reminders = resp.json()
            for r in all_reminders:
                due_str = r.get("due_at")
                if not due_str:
                    continue
                try:
                    due_dt = datetime.fromisoformat(due_str)
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=timezone.utc)
                    due_oslo = due_dt.astimezone(_TZ)
                    recurrence = r.get("recurrence")
                    if recurrence == "daily":
                        reminders.append(r)
                    elif recurrence and recurrence.startswith("weekly:"):
                        day_abbr = recurrence.split(":", 1)[1].upper()[:3]
                        _WEEKDAY_ABBR = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                        if _WEEKDAY_ABBR[today.weekday()] == day_abbr:
                            reminders.append(r)
                    elif due_oslo.date() == today:
                        reminders.append(r)
                except (ValueError, TypeError):
                    pass
        except Exception:
            log.exception("Failed to fetch reminders from orchestrator")

    weekday = today.weekday()
    return jsonify({
        "date": today.isoformat(),
        "day_name": _DAY_NAMES[weekday],
        "month_name": _MONTH_NAMES[today.month],
        "events": events,
        "reminders": reminders,
    })

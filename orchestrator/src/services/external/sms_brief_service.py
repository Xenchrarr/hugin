from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from src.api.hugin_core.today import get_today
from src.persistence.UserStorage import UserStorage
from src.services.core.message_hub_service import MessageHubService

_TZ = ZoneInfo("Europe/Oslo")
_CORE_URL = os.environ.get("CORE_API_URL", "http://hugin-core:5100").rstrip("/")


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


def format_sms_brief(data: dict, weather: str = "", power: str = "") -> str:
    events = data.get("events") or []
    reminders = data.get("reminders") or []
    lines = [datetime.now(_TZ).strftime("%a %d %b")]
    lines.append("Cal: " + ("; ".join(
        f"{_time(item.get('start', ''))} {item.get('summary', '(untitled)')}" for item in events
    ) if events else "clear"))
    if reminders:
        lines.append("Rem: " + "; ".join(
            f"{_time(item.get('due_at', ''))} {item.get('title', 'Reminder')}" for item in reminders
        ))
    if weather:
        lines.append("Wx: " + weather.replace("Now: ", "", 1))
    if power:
        lines.append("Power: " + power)
    return "\n".join(lines)


def run_sms_brief(param: str = "") -> None:
    config = json.loads(param or "{}")
    phone = str(config.get("phone") or "").strip()
    user_id = int(config.get("user_id") or 0)
    if not phone or not user_id:
        raise ValueError("sms_brief requires phone and user_id")
    user = UserStorage().get_user(user_id)
    user_config = (user.config or {}) if user else {}
    weather = ""
    location_id = user_config.get("weather_location_id", "")
    if location_id:
        try:
            response = requests.get(f"{_CORE_URL}/api/weather/{location_id}/summary", timeout=(5, 15))
            response.raise_for_status()
            weather = response.json().get("text", "")
        except Exception:
            pass
    power = ""
    try:
        response = requests.get(f"{_CORE_URL}/api/power/growatt", timeout=(5, 15))
        response.raise_for_status()
        values = response.json()
        power = f"{values.get('currentPower', '?')}W, {values.get('todayEnergy', '?')}kWh"
    except Exception:
        pass
    now = datetime.now(_TZ)
    MessageHubService.instance().submit_sms(
        phone_number=phone,
        message=format_sms_brief(get_today(), weather, power),
        source_type="system",
        source_key="daily-brief",
        source_label="Daily brief",
        user_id=user_id,
        idempotency_key=f"daily-brief:{user_id}:{now:%Y%m%d}",
    )

import logging
from datetime import date, datetime, timedelta, timezone

import requests
import recurring_ical_events
from icalendar import Calendar

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    def __init__(self) -> None:
        from src.config import settings

        self._ical_urls = settings.GOOGLE_CALENDAR_ICAL_URLS

    def get_events(self, days: int = 7, urls: list[str] | None = None) -> list[dict]:
        effective_urls = urls if urls is not None else self._ical_urls
        if not effective_urls:
            return []

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days)

        all_events: list[dict] = []
        for url in effective_urls:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                cal = Calendar.from_ical(response.content)
                calendar_name = str(cal.get("X-WR-CALNAME", url))
                events = recurring_ical_events.of(cal).between(now, time_max)
                for component in events:
                    dtstart = component.get("DTSTART")
                    dtend = component.get("DTEND")
                    if dtstart is None:
                        continue
                    start_val = dtstart.dt
                    end_val = dtend.dt if dtend else start_val
                    all_day = isinstance(start_val, date) and not isinstance(start_val, datetime)
                    if all_day:
                        start_str = start_val.isoformat()
                        end_str = end_val.isoformat()
                    else:
                        if start_val.tzinfo is None:
                            start_val = start_val.replace(tzinfo=timezone.utc)
                        if end_val.tzinfo is None:
                            end_val = end_val.replace(tzinfo=timezone.utc)
                        start_str = start_val.isoformat()
                        end_str = end_val.isoformat()
                    all_events.append(
                        {
                            "start": start_str,
                            "end": end_str,
                            "summary": str(component.get("SUMMARY", "(no title)")),
                            "calendar_name": calendar_name,
                            "all_day": all_day,
                            "source_url": url,
                        }
                    )
            except Exception:
                logger.exception("Failed to fetch events from iCal URL %s", url)

        all_events.sort(key=lambda e: e["start"])
        return all_events

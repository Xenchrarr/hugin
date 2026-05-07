import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class GoogleCalendarClient:
    def __init__(self) -> None:
        from src.config import settings

        self._service_account_json = settings.GOOGLE_SERVICE_ACCOUNT_JSON
        self._calendar_ids = settings.GOOGLE_CALENDAR_IDS
        self._service = None

    def _build_service(self):
        if self._service is not None:
            return self._service
        if not self._service_account_json:
            logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
            return None
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            info = json.loads(self._service_account_json)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=_SCOPES
            )
            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except Exception:
            logger.exception("Failed to build Google Calendar service")
            return None

    def _get_calendar_name(self, service, calendar_id: str) -> str:
        try:
            cal = service.calendars().get(calendarId=calendar_id).execute()
            return cal.get("summary", calendar_id)
        except Exception:
            logger.warning("Could not fetch name for calendar %s", calendar_id)
            return calendar_id

    def get_events(self, days: int = 7) -> list[dict]:
        service = self._build_service()
        if service is None or not self._calendar_ids:
            return []

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days)).isoformat()

        all_events: list[dict] = []
        for cal_id in self._calendar_ids:
            try:
                name = self._get_calendar_name(service, cal_id)
                result = (
                    service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
                for item in result.get("items", []):
                    start = item.get("start", {})
                    end = item.get("end", {})
                    all_day = "date" in start and "dateTime" not in start
                    all_events.append(
                        {
                            "start": start.get("dateTime") or start.get("date", ""),
                            "end": end.get("dateTime") or end.get("date", ""),
                            "summary": item.get("summary", "(no title)"),
                            "calendar_name": name,
                            "all_day": all_day,
                        }
                    )
            except Exception:
                logger.exception("Failed to fetch events for calendar %s", cal_id)

        all_events.sort(key=lambda e: e["start"])
        return all_events

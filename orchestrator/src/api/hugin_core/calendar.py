from src.api.hugin_core import CORE_API_URL, session


def get_calendar_agenda(urls: list[str], days: int = 7) -> list[dict]:
    params = {"days": days, "urls": ",".join(urls)}
    response = session.get(f"{CORE_API_URL}/api/calendar/agenda", params=params, timeout=15)
    response.raise_for_status()
    return response.json().get("events", [])

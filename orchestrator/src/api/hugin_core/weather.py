from src.api.hugin_core import CORE_API_URL, session


def get_weather_image(yr_id: str) -> bytes:
    response = session.get(f"{CORE_API_URL}/api/weather/{yr_id}", params={"dark": "false"}, timeout=20)
    response.raise_for_status()
    return response.content

from src.api.hugin_core import CORE_API_URL, session


def get_today() -> dict:
    response = session.get(f"{CORE_API_URL}/api/today/", timeout=15)
    response.raise_for_status()
    return response.json()

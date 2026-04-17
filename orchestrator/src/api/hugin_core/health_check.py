from . import session, CORE_API_URL


def check_hugin_core_health():
    url = f"{CORE_API_URL}/api/power/current"
    response = session.get(url, timeout=5)
    if response.status_code == 200:
        return True
    else:
        return False

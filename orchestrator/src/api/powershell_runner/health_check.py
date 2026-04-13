from . import session, POWERSHELL_API_ENDPOINT
from src.persistence.DatabaseLogger import DatabaseLogger

def check_if_powershell_script_engine_is_up():
    url = f"{POWERSHELL_API_ENDPOINT}/test"
    # print(f"testing: {url}")
    response = session.get(url)
    if response.status_code == 200:
        return True
    else:
        return False


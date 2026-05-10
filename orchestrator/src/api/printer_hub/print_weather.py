import logging

from . import session, PRINTER_HUB_URL, PRINTER_HUB_TIMEOUT

log = logging.getLogger(__name__)


def send_print_weather(yr_id: str = None) -> dict:
    url = f"{PRINTER_HUB_URL}/api/print/weather"
    log.info("Sending print_weather request to %s (yr_id=%s)", url, yr_id or "from env")

    body = {"yr_id": yr_id} if yr_id else {}
    response = session.post(url, json=body, timeout=PRINTER_HUB_TIMEOUT)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"print_weather failed: {response.status_code}: {response.text}")

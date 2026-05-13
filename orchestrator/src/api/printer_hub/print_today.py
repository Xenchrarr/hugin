import logging

from . import session, PRINTER_HUB_URL, PRINTER_HUB_TIMEOUT

log = logging.getLogger(__name__)


def send_print_today() -> dict:
    url = f"{PRINTER_HUB_URL}/api/print/today"
    log.info("Sending print_today request to %s", url)

    response = session.post(url, timeout=PRINTER_HUB_TIMEOUT)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"print_today failed: {response.status_code}: {response.text}")

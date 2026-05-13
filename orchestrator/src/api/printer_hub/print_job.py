import logging

from . import session, PRINTER_HUB_URL, PRINTER_HUB_TIMEOUT

log = logging.getLogger(__name__)


def send_print_content(lines: list, title: str = "", footer: str = "") -> dict:
    url = f"{PRINTER_HUB_URL}/api/print/"
    log.info("Sending print_content request to %s (lines=%d)", url, len(lines))

    body = {"lines": lines, "title": title, "footer": footer}
    response = session.post(url, json=body, timeout=PRINTER_HUB_TIMEOUT)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"print_content failed: {response.status_code}: {response.text}")


def send_print_news(feed_url: str, count: int = 5) -> dict:
    url = f"{PRINTER_HUB_URL}/api/print/news"
    log.info("Sending print_news request to %s (feed=%s, count=%d)", url, feed_url, count)

    body = {"feed_url": feed_url, "count": count}
    response = session.post(url, json=body, timeout=PRINTER_HUB_TIMEOUT)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"print_news failed: {response.status_code}: {response.text}")

import logging
import os
import base64

import requests

logger = logging.getLogger(__name__)

_PRINTER_HUB_URL = os.environ.get("PRINTER_HUB_URL", "http://printer-hub:6002")


class PrinterHubClient:
    def __init__(self, base_url: str = _PRINTER_HUB_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def print_content(self, lines: list[str], title: str = "", footer: str = "") -> bool:
        try:
            response = requests.post(
                f"{self._base_url}/api/print/",
                json={"lines": lines, "title": title, "footer": footer},
                timeout=(5, 30),
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("PrinterHub API error: POST /api/print/")
            return False

    def print_image(self, image_bytes: bytes) -> bool:
        try:
            response = requests.post(
                f"{self._base_url}/api/print/image",
                json={"image_b64": base64.b64encode(image_bytes).decode("ascii")},
                timeout=(5, 60),
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("PrinterHub API error: POST /api/print/image")
            return False


_client = PrinterHubClient()


def print_content(lines: list[str], title: str = "", footer: str = "") -> bool:
    return _client.print_content(lines, title, footer)


def print_image(image_bytes: bytes) -> bool:
    return _client.print_image(image_bytes)

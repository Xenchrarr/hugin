import logging
import os

import requests

logger = logging.getLogger(__name__)

_PRINTER_HUB_URL = os.environ.get("PRINTER_HUB_URL", "http://printer-hub:6002")


class PrinterHubClient:
    def __init__(self, base_url: str = _PRINTER_HUB_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def print_shopping_list(self) -> bool:
        try:
            response = requests.post(f"{self._base_url}/api/print/shopping", timeout=(5, 30))
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("PrinterHub API error: POST /api/print/shopping")
            return False


_client = PrinterHubClient()


def print_shopping_list() -> bool:
    return _client.print_shopping_list()

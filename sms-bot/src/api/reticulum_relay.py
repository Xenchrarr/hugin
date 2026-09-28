import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_RETICULUM_RELAY_URL = os.environ.get(
    "RETICULUM_RELAY_URL", "http://reticulum-relay:8082"
)
_SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


def _headers() -> dict[str, str]:
    return {"X-Service-Key": _SERVICE_KEY} if _SERVICE_KEY else {}


class ReticulumRelayClient:
    def __init__(self, base_url: str = _RETICULUM_RELAY_URL) -> None:
        self._base = base_url.rstrip("/")

    def get_conversations(self) -> list[dict]:
        try:
            response = requests.get(
                f"{self._base}/api/reticulum/conversations",
                headers=_headers(),
                timeout=(5, 15),
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("ReticulumRelayClient: get_conversations failed")
            return []

    def send_message(self, destination_hash: str, text: str) -> bool:
        try:
            response = requests.post(
                f"{self._base}/api/reticulum/send",
                json={
                    "destination_hash": destination_hash,
                    "text": text,
                    "delivery_method": "direct",
                },
                headers=_headers(),
                timeout=(5, 60),
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.exception(
                "ReticulumRelayClient: send_message to %s failed", destination_hash
            )
            return False

    def get_context(self, phone: str) -> Optional[dict]:
        try:
            response = requests.get(
                f"{self._base}/api/reticulum/context/"
                f"{requests.utils.quote(phone, safe='')}",
                headers=_headers(),
                timeout=(5, 10),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("ReticulumRelayClient: get_context failed")
            return None

    def set_context(self, phone: str, destination_hash: str) -> bool:
        try:
            response = requests.post(
                f"{self._base}/api/reticulum/context",
                json={"phone": phone, "destination_hash": destination_hash},
                headers=_headers(),
                timeout=(5, 10),
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("ReticulumRelayClient: set_context failed")
            return False


import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_MESSENGER_RELAY_URL = os.environ.get("MESSENGER_RELAY_URL", "http://messenger-relay:8081")
_SERVICE_KEY = os.environ.get("MESSENGER_RELAY_SERVICE_KEY") or os.environ.get("SERVICE_KEY", "")


def _headers() -> dict[str, str]:
    return {"X-Service-Key": _SERVICE_KEY} if _SERVICE_KEY else {}


class MessengerRelayClient:
    def __init__(self, base_url: str = _MESSENGER_RELAY_URL) -> None:
        self._base = base_url.rstrip("/")

    def get_conversations(self) -> list[dict]:
        try:
            response = requests.get(
                f"{self._base}/api/messenger/conversations", headers=_headers(), timeout=(5, 15)
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("MessengerRelayClient: get_conversations failed")
            return []

    def send_message(self, thread_id: str, text: str) -> bool:
        try:
            response = requests.post(
                f"{self._base}/api/messenger/send",
                json={"thread_id": thread_id, "text": text},
                headers=_headers(),
                timeout=(5, 60),
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("MessengerRelayClient: send_message to %s failed", thread_id)
            return False

    def get_context(self, phone: str) -> Optional[dict]:
        try:
            response = requests.get(
                f"{self._base}/api/messenger/context/{requests.utils.quote(phone, safe='')}",
                headers=_headers(),
                timeout=(5, 10),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("MessengerRelayClient: get_context failed")
            return None

    def set_context(self, phone: str, thread_id: str) -> bool:
        try:
            response = requests.post(
                f"{self._base}/api/messenger/context",
                json={"phone": phone, "thread_id": thread_id},
                headers=_headers(),
                timeout=(5, 10),
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("MessengerRelayClient: set_context failed")
            return False

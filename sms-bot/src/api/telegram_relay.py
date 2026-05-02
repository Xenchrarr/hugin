import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_RELAY_URL = os.environ.get("TELEGRAM_RELAY_URL", "http://telegram-relay:8080")
_SERVICE_KEY = os.environ.get("TELEGRAM_RELAY_SERVICE_KEY", "")


def _headers() -> dict:
    return {"X-Service-Key": _SERVICE_KEY} if _SERVICE_KEY else {}


class TelegramRelayClient:
    def __init__(self, base_url: str = _TELEGRAM_RELAY_URL) -> None:
        self._base = base_url.rstrip("/")

    def get_conversations(self) -> list[dict]:
        """Return list of recent conversations (sorted newest-first, index 1-based)."""
        try:
            resp = requests.get(
                f"{self._base}/api/telegram/conversations",
                headers=_headers(),
                timeout=(5, 15),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("TelegramRelayClient: get_conversations failed")
            return []

    def send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a Telegram chat. Returns True on success."""
        try:
            resp = requests.post(
                f"{self._base}/api/telegram/send",
                json={"chat_id": chat_id, "text": text},
                headers=_headers(),
                timeout=(5, 30),
            )
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("TelegramRelayClient: send_message to chat %s failed", chat_id)
            return False

    def get_context(self, phone: str) -> Optional[dict]:
        """Return {chat_id, title} for the sticky reply target, or None."""
        try:
            resp = requests.get(
                f"{self._base}/api/telegram/context/{requests.utils.quote(phone, safe='')}",
                headers=_headers(),
                timeout=(5, 10),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("TelegramRelayClient: get_context for %s failed", phone)
            return None

    def set_context(self, phone: str, chat_id: int) -> bool:
        """Set the sticky reply target for a phone number."""
        try:
            resp = requests.post(
                f"{self._base}/api/telegram/context",
                json={"phone": phone, "chat_id": chat_id},
                headers=_headers(),
                timeout=(5, 10),
            )
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("TelegramRelayClient: set_context failed")
            return False

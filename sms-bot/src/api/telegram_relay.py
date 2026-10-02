import logging
import os
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_RELAY_URL = os.environ.get("TELEGRAM_RELAY_URL", "http://telegram-relay:8080")
_SERVICE_KEY = os.environ.get("TELEGRAM_RELAY_SERVICE_KEY") or os.environ.get("SERVICE_KEY", "")


@dataclass(frozen=True)
class IntegrationSendResult:
    status: str
    external_message_id: str | None = None
    detail: str | None = None


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

    def send_routed_message(
        self, chat_id: int, text: str, reply_to_message_id: str | int | None = None
    ) -> IntegrationSendResult:
        """Send once and distinguish a definite failure from an ambiguous timeout."""
        payload = {"chat_id": chat_id, "text": text}
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = int(reply_to_message_id)
        try:
            response = requests.post(
                f"{self._base}/api/telegram/send", json=payload,
                headers=_headers(), timeout=(5, 30),
            )
            response.raise_for_status()
            data = response.json()
            message_id = data.get("message_id")
            return IntegrationSendResult(
                "accepted", str(message_id) if message_id is not None else None
            )
        except requests.ReadTimeout as exc:
            logger.warning("Telegram send timed out after submission: %s", exc)
            return IntegrationSendResult("uncertain", detail="integration response timed out")
        except (requests.ConnectTimeout, requests.ConnectionError) as exc:
            logger.warning("Telegram integration unavailable: %s", exc)
            return IntegrationSendResult("failed", detail="integration unavailable")
        except requests.RequestException as exc:
            logger.warning("Telegram rejected routed message: %s", exc)
            return IntegrationSendResult("failed", detail="integration rejected message")
        except Exception as exc:
            logger.warning("Telegram returned an unusable send response: %s", exc)
            return IntegrationSendResult("uncertain", detail="invalid integration response")

    def send_media(
        self,
        chat_id: int,
        media_bytes: bytes,
        media_mime_type: str,
        caption: str = "",
    ) -> bool:
        """Send an image and optional caption to a Telegram chat."""
        extensions = {
            "image/jpeg": "photo.jpg",
            "image/png": "photo.png",
            "image/gif": "photo.gif",
        }
        filename = extensions.get(media_mime_type.lower())
        if filename is None:
            logger.error("TelegramRelayClient: unsupported media type %s", media_mime_type)
            return False
        try:
            resp = requests.post(
                f"{self._base}/api/telegram/send-media",
                data={"chat_id": str(chat_id), "caption": caption},
                files={"media": (filename, media_bytes, media_mime_type)},
                headers=_headers(),
                timeout=(5, 120),
            )
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("TelegramRelayClient: send_media to chat %s failed", chat_id)
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

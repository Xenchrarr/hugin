import asyncio
import logging
import os

import httpx

from app.destinations.base import AbstractDestination

logger = logging.getLogger(__name__)

_SMS_BOT_URL = os.environ.get("SMS_BOT_URL", "http://sms-hub:5050")


class SmsAdapter(AbstractDestination):
    """Forwards a message as an SMS by calling the sms-hub service."""

    def __init__(self, destination_id: str, config: dict) -> None:
        self._id = destination_id
        self._phone: str = config.get("phone", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def phone(self) -> str:
        return self._phone

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15)
        return self._client

    @staticmethod
    def _format_message(payload: dict) -> str:
        chat_title = (payload.get("chat_title") or "")[:8] or None
        sender_name = (payload.get("sender_name") or "")[:8] or None
        chat_type = payload.get("chat_type", "")
        text = payload.get("text") or payload.get("caption") or f"<{payload.get('media_type', 'media')}>"

        # For private chats chat_title IS the contact's name — same as sender_name.
        # Showing both would produce "Alice | Alice: hi", so use a single label.
        if chat_type == "private":
            label = sender_name or chat_title
            if label:
                return f"{label}: {text}"
            return text

        # Groups: show chat name and, when available, who sent it
        if chat_title and sender_name:
            return f"{chat_title} | {sender_name}: {text}"
        if chat_title:
            return f"{chat_title}: {text}"
        if sender_name:
            return f"{sender_name}: {text}"
        return text

    async def send(self, payload: dict) -> None:
        if not self._phone:
            logger.error("SmsAdapter '%s': no phone number configured", self._id)
            return

        body = self._format_message(payload)
        client = self._get_client()

        # If the payload carries media bytes, send as MMS
        if payload.get("media_data"):
            url = f"{_SMS_BOT_URL}/api/sms/mms/send"
            mms_body = {
                "phone": self._phone,
                "message": body,
                "media_data": payload["media_data"],
                "media_mime_type": payload.get("media_mime_type", "image/jpeg"),
            }
            try:
                resp = await client.post(url, json=mms_body)
                resp.raise_for_status()
                logger.debug("SmsAdapter '%s' delivered MMS to %s", self._id, self._phone)
            except httpx.HTTPError as exc:
                logger.error("SmsAdapter '%s' MMS failed: %s", self._id, exc)
            return

        url = f"{_SMS_BOT_URL}/api/sms/send"
        try:
            resp = await client.post(url, json={"phone": self._phone, "message": body})
            resp.raise_for_status()
            logger.debug("SmsAdapter '%s' delivered to %s", self._id, self._phone)
        except httpx.HTTPError as exc:
            logger.error("SmsAdapter '%s' failed: %s", self._id, exc)

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

import logging
import os

import httpx

from app.destinations.base import AbstractDestination

logger = logging.getLogger(__name__)

_ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_API_URL", "http://orchestrator:6000").rstrip("/")
_SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


class SmsAdapter(AbstractDestination):
    """Queues an SMS delivery in Message Hub."""

    def __init__(self, destination_id: str, config: dict) -> None:
        self._id = destination_id
        self._phone: str = config.get("phone", "")
        self._recovery_policy: str = config.get("recovery_policy", "digest_hold")
        if self._recovery_policy not in {"replay", "digest_hold", "inbox_only", "latest_only"}:
            self._recovery_policy = "digest_hold"
        try:
            self._priority = min(max(int(config.get("priority", 40)), 0), 100)
        except (TypeError, ValueError):
            self._priority = 40
        self._client: httpx.AsyncClient | None = None

    @property
    def phone(self) -> str:
        return self._phone

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=330)
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

        chat_id = payload.get("chat_id")
        message_id = payload.get("message_id")
        source_label = payload.get("chat_title") or payload.get("sender_name") or "Telegram"
        idempotency_key = f"telegram:{chat_id}:{message_id}:{self._phone}"
        url = f"{_ORCHESTRATOR_URL}/api/message-hub/messages"
        delivery: dict = {
            "gateway_key": "sms-main",
            "address": {"phone": self._phone},
            "recovery_policy": self._recovery_policy,
            "priority": self._priority,
            "idempotency_key": idempotency_key,
        }
        if self._id.isdigit():
            delivery["target_endpoint_id"] = int(self._id)
        request_body = {
            "direction": "outbound",
            "kind": "text",
            "source_gateway_key": "telegram-main",
            "external_id": f"{chat_id}:{message_id}",
            "conversation_key": str(chat_id) if chat_id is not None else None,
            "payload": {"text": body},
            "metadata": {
                "source_type": "telegram",
                "source_label": source_label,
                "chat_id": chat_id,
                "message_id": message_id,
            },
            "priority": self._priority,
            "idempotency_key": idempotency_key,
            "deliveries": [delivery],
        }
        headers = {"X-Service-Key": _SERVICE_KEY} if _SERVICE_KEY else {}
        try:
            resp = await client.post(url, json=request_body, headers=headers)
            resp.raise_for_status()
            response_data = resp.json()
            status = response_data.get("status") or (
                "queued" if response_data.get("message_id") else "accepted"
            )
            logger.debug("SmsAdapter '%s' %s for %s", self._id, status, self._phone)
        except httpx.HTTPError as exc:
            logger.error("SmsAdapter '%s' could not submit message: %s", self._id, exc)

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

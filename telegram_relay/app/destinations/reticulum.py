import logging
import os

import httpx

from app.destinations.base import AbstractDestination

logger = logging.getLogger(__name__)

_ORCHESTRATOR_URL = os.environ.get(
    "ORCHESTRATOR_API_URL", "http://orchestrator:6000"
).rstrip("/")
_SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


class ReticulumAdapter(AbstractDestination):
    """Queue a Telegram message for an LXMF destination."""

    def __init__(self, destination_id: str, config: dict) -> None:
        self._id = destination_id
        self._destination_hash = str(config.get("destination_hash") or "").strip().lower()
        self._delivery_method = str(config.get("delivery_method") or "direct").strip().lower()
        self._recovery_policy = str(config.get("recovery_policy") or "replay")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"X-Service-Key": _SERVICE_KEY} if _SERVICE_KEY else {}
            self._client = httpx.AsyncClient(headers=headers, timeout=30)
        return self._client

    async def send(self, payload: dict) -> None:
        if not self._destination_hash:
            raise ValueError(f"Reticulum destination {self._id!r} has no destination_hash")
        text = payload.get("text") or payload.get("caption") or "<message>"
        chat_title = payload.get("chat_title")
        sender_name = payload.get("sender_name")
        labels = [item for item in (chat_title, sender_name) if item]
        if payload.get("chat_type") == "private" and labels:
            labels = labels[:1]
        formatted = f"{' / '.join(labels)}: {text}" if labels else str(text)
        chat_id = payload.get("chat_id")
        message_id = payload.get("message_id")
        idempotency_key = (
            f"telegram:{chat_id}:{message_id}:reticulum:{self._destination_hash}"
        )
        delivery = {
            "gateway_key": "reticulum-main",
            "target_endpoint_id": int(self._id) if self._id.isdigit() else None,
            "address": {
                "destination_hash": self._destination_hash,
                "delivery_method": self._delivery_method,
            },
            "recovery_policy": self._recovery_policy,
            "idempotency_key": idempotency_key,
        }
        body = {
            "direction": "outbound",
            "kind": "text",
            "source_gateway_key": "telegram-main",
            "external_id": f"{chat_id}:{message_id}",
            "conversation_key": str(chat_id),
            "payload": {"text": formatted},
            "metadata": {
                "source_type": "telegram",
                "source_label": chat_title or sender_name or "Telegram",
                "chat_id": chat_id,
                "message_id": message_id,
            },
            "idempotency_key": idempotency_key,
            "deliveries": [delivery],
        }
        response = await self._get_client().post(
            f"{_ORCHESTRATOR_URL}/api/message-hub/messages", json=body
        )
        response.raise_for_status()

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


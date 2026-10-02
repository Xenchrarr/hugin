import base64
import logging
import os
import re
import unicodedata

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
        self._owner_user_id = config.get("owner_user_id")
        self._integration_account = str(
            config.get("integration_account") or "telegram-main"
        )
        self._conversation_aliases = {
            str(key): str(value).strip().lower()
            for key, value in (config.get("conversation_aliases") or {}).items()
        }
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
    def _slug(value: str) -> str:
        ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9_-]+", "-", ascii_value.lower()).strip("-_")
        return (slug or "chat")[:18]

    def _alias_for(self, payload: dict) -> str:
        chat_id = str(payload.get("chat_id"))
        configured = self._conversation_aliases.get(chat_id)
        if configured:
            return configured
        title = str(payload.get("chat_title") or payload.get("sender_name") or chat_id)
        return f"tg/{self._slug(title)}"

    async def _register_message(self, payload: dict) -> dict | None:
        chat_id = payload.get("chat_id")
        message_id = payload.get("message_id")
        text = payload.get("text") or payload.get("caption") or f"<{payload.get('media_type', 'media')}>"
        body = {
            "owner_phone": self._phone,
            "service": "tg",
            "integration_account": self._integration_account,
            "external_chat_id": str(chat_id),
            "alias": self._alias_for(payload),
            "display_name": payload.get("chat_title") or payload.get("sender_name") or str(chat_id),
            "event_id": f"tg:{self._integration_account}:{chat_id}:{message_id}",
            "external_message_id": str(message_id),
            "body": text,
            "author": (payload.get("sender_name")
                       if payload.get("chat_type") != "private" else None),
        }
        if self._owner_user_id is not None:
            body["owner_user_id"] = self._owner_user_id
        client = self._get_client()
        try:
            response = await client.post(
                f"{_ORCHESTRATOR_URL}/api/sms-routing/external-messages",
                json=body,
                headers={"X-Service-Key": _SERVICE_KEY} if _SERVICE_KEY else {},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error("SmsAdapter '%s' could not allocate reply reference: %s", self._id, exc)
            return None

    async def send(self, payload: dict) -> None:
        if not self._phone:
            logger.error("SmsAdapter '%s': no phone number configured", self._id)
            return

        routed = await self._register_message(payload)
        if routed is None:
            return
        body = routed["text"]
        client = self._get_client()
        media_data = payload.get("media_data")
        media_mime_type = str(payload.get("media_mime_type") or "image/jpeg").lower()
        is_mms = isinstance(media_data, bytes) and bool(media_data)

        chat_id = payload.get("chat_id")
        message_id = payload.get("message_id")
        source_label = payload.get("chat_title") or payload.get("sender_name") or "Telegram"
        idempotency_key = (
            f"telegram:{self._integration_account}:{chat_id}:{message_id}:{self._phone}"
        )
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
            "kind": "mms" if is_mms else "text",
            "source_gateway_key": "telegram-main",
            "external_id": f"{self._integration_account}:{chat_id}:{message_id}",
            "conversation_key": (
                f"{self._integration_account}:{chat_id}" if chat_id is not None else None
            ),
            "payload": {"text": body},
            "metadata": {
                "source_type": "telegram",
                "source_label": source_label,
                "chat_id": chat_id,
                "message_id": message_id,
                "sms_reference": routed["reference"],
                "conversation_alias": routed["alias"],
            },
            "priority": self._priority,
            "idempotency_key": idempotency_key,
            "deliveries": [delivery],
        }
        if is_mms:
            extension = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/gif": "gif",
            }.get(media_mime_type, "bin")
            request_body["attachments"] = [{
                "data_base64": base64.b64encode(media_data).decode("ascii"),
                "content_type": media_mime_type,
                "filename": f"telegram-{message_id}.{extension}",
            }]
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

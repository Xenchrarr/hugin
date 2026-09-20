from __future__ import annotations

import base64
import os
from typing import Any

import requests

from src.models.orchestrator.MessageHub import (
    MessageAttachment,
    MessageDelivery,
    MessageGateway,
)


SMS_BOT_URL = os.environ.get("SMS_BOT_URL", "http://sms-hub:5050").rstrip("/")
TELEGRAM_RELAY_URL = os.environ.get(
    "TELEGRAM_RELAY_URL", "http://telegram-relay:8080"
).rstrip("/")
SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


class GatewayDeliveryUncertainError(RuntimeError):
    """The gateway may have handed the message to its transport."""


class MessageGatewayClient:
    """Protocol adapter used by the message-hub delivery worker."""

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"X-Service-Key": SERVICE_KEY} if SERVICE_KEY else {}

    def send(
        self,
        delivery: MessageDelivery,
        attachments: list[MessageAttachment] | None = None,
    ) -> str | None:
        gateway_type = delivery.gateway_type
        if gateway_type == "sms":
            return self._send_sms(delivery, attachments or [])
        if attachments:
            raise ValueError(f"Attachments are not supported by {gateway_type} gateways")
        if gateway_type == "telegram":
            return self._send_telegram(delivery)
        if gateway_type == "webhook":
            return self._send_webhook(delivery)
        raise ValueError(f"Unsupported gateway type: {gateway_type}")

    def check_ready(self, gateway: MessageGateway) -> tuple[bool, str] | None:
        """Return readiness or None when the gateway has no active probe."""
        try:
            if gateway.type == "sms":
                base_url = str(gateway.config.get("base_url") or SMS_BOT_URL).rstrip("/")
                response = requests.get(f"{base_url}/api/sms/health/ready", timeout=(3, 10))
                data = response.json() if response.content else {}
                ready = response.status_code == 200 and bool(data.get("ready"))
                return ready, "" if ready else str(data.get("error") or response.status_code)

            if gateway.type == "telegram":
                base_url = str(gateway.config.get("base_url") or TELEGRAM_RELAY_URL).rstrip("/")
                response = requests.get(
                    f"{base_url}/health",
                    headers=self._headers(),
                    timeout=(3, 10),
                )
                response.raise_for_status()
                return True, ""
        except Exception as exc:
            return False, str(exc)
        return None

    def _send_sms(
        self,
        delivery: MessageDelivery,
        attachments: list[MessageAttachment],
    ) -> str | None:
        phone = str(delivery.address.get("phone") or "").strip()
        text = str(delivery.payload.get("text") or delivery.payload.get("message") or "").strip()
        if not phone:
            raise ValueError("SMS delivery requires address.phone")
        base_url = str((delivery.gateway_config or {}).get("base_url") or SMS_BOT_URL).rstrip("/")
        if attachments:
            if len(attachments) != 1:
                raise ValueError("MMS delivery requires exactly one attachment")
            attachment = attachments[0]
            response = requests.post(
                f"{base_url}/api/sms/mms/send",
                json={
                    "phone": phone,
                    "message": text,
                    "delivery_token": delivery.dispatch_token,
                    "media_data": base64.b64encode(attachment.content).decode("ascii"),
                    "media_mime_type": attachment.content_type,
                },
                headers=self._headers(),
                timeout=(5, 330),
            )
            self._raise_for_delivery_status(response)
            data = response.json() if response.content else {}
            return str(data.get("message_id") or "") or None
        if not text:
            raise ValueError("SMS delivery requires payload.text")
        response = requests.post(
            f"{base_url}/api/sms/send",
            json={
                "phone": phone,
                "message": text,
                "delivery_token": delivery.dispatch_token,
            },
            headers=self._headers(),
            timeout=(5, 330),
        )
        self._raise_for_delivery_status(response)
        data = response.json() if response.content else {}
        return str(data.get("message_id") or "") or None

    @staticmethod
    def _raise_for_delivery_status(response) -> None:
        if response.status_code == 409:
            try:
                data = response.json()
            except ValueError:
                data = {}
            if data.get("delivery_state") == "uncertain":
                raise GatewayDeliveryUncertainError(
                    str(data.get("error") or "gateway delivery outcome is uncertain")
                )
        response.raise_for_status()

    def _send_telegram(self, delivery: MessageDelivery) -> str | None:
        text = str(delivery.payload.get("text") or delivery.payload.get("message") or "").strip()
        if not text:
            raise ValueError("Telegram delivery requires payload.text")
        base_url = str(
            (delivery.gateway_config or {}).get("base_url") or TELEGRAM_RELAY_URL
        ).rstrip("/")
        if delivery.address.get("self"):
            path = "/api/telegram/send-self"
            body: dict[str, Any] = {"text": text}
        else:
            chat_id = delivery.address.get("chat_id")
            if chat_id is None:
                raise ValueError("Telegram delivery requires address.chat_id")
            path = "/api/telegram/send"
            body = {"chat_id": int(chat_id), "text": text}
        response = requests.post(
            f"{base_url}{path}",
            json=body,
            headers=self._headers(),
            timeout=(5, 60),
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        return str(data.get("message_id") or "") or None

    def _send_webhook(self, delivery: MessageDelivery) -> str | None:
        url = str(delivery.address.get("url") or "").strip()
        if not url:
            raise ValueError("Webhook delivery requires address.url")
        headers = delivery.address.get("headers") or {}
        if not isinstance(headers, dict):
            raise ValueError("Webhook address.headers must be an object")
        timeout = min(max(float(delivery.address.get("timeout", 15)), 1), 120)
        response = requests.post(url, json=delivery.payload, headers=headers, timeout=(5, timeout))
        response.raise_for_status()
        return response.headers.get("X-Request-Id")

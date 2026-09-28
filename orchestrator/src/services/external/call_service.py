from __future__ import annotations

import os
import uuid

import requests

from src.services.core.auth_service import SERVICE_KEY


SMS_BOT_URL = os.environ.get("SMS_BOT_URL", "http://sms-hub:5050").rstrip("/")


def ring_phone(phone: str, ring_seconds: int = 20, attempt_token: str | None = None) -> dict:
    """Ask the cellular modem service to place a short ring-only call."""
    if not SERVICE_KEY:
        raise RuntimeError("Service authentication is not configured")

    response = requests.post(
        f"{SMS_BOT_URL}/api/calls/ring",
        json={"phone": phone, "ring_seconds": ring_seconds,
              "attempt_token": attempt_token or f"manual-{uuid.uuid4().hex}"},
        headers={"X-Service-Key": SERVICE_KEY},
        timeout=(5, ring_seconds + 60),
    )
    response.raise_for_status()
    return response.json()


def cancel_call() -> bool:
    response = requests.post(
        f"{SMS_BOT_URL}/api/calls/cancel",
        headers={"X-Service-Key": SERVICE_KEY}, timeout=(5, 10),
    )
    return response.ok


def voice_health() -> dict:
    response = requests.get(
        f"{SMS_BOT_URL}/api/calls/health",
        headers={"X-Service-Key": SERVICE_KEY}, timeout=(5, 15),
    )
    data = response.json()
    data["http_status"] = response.status_code
    return data

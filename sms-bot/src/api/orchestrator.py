import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ORCHESTRATOR_API_URL = os.environ.get("ORCHESTRATOR_API_URL", "http://orchestrator:6000")
_SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


class OrchestratorClient:
    def __init__(self, base_url: str = ORCHESTRATOR_API_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {"X-Service-Key": _SERVICE_KEY} if _SERVICE_KEY else {}

    def _get(self, path: str, **params) -> dict | list | None:
        try:
            resp = requests.get(f"{self._base_url}{path}", params=params, headers=self._headers(), timeout=(5, 15))
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Orchestrator API error: GET %s", path)
            return None

    def _post(self, path: str, json: dict | None = None) -> dict | None:
        try:
            resp = requests.post(f"{self._base_url}{path}", json=json or {}, headers=self._headers(), timeout=(5, 15))
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Orchestrator API error: POST %s", path)
            return None

    # ── Reminders ────────────────────────────────────────────

    def create_reminder(self, title: str, due_at: str, message: str = None,
                        recurrence: str = None, recipient_ids: list[int] = None,
                        user_id: int = None, created_by: str = "sms") -> dict | None:
        payload = {
            "title": title,
            "due_at": due_at,
            "message": message,
            "recurrence": recurrence,
            "recipient_ids": recipient_ids,
            "user_id": user_id,
            "created_by": created_by,
        }
        return self._post("/api/reminders/", json=payload)

    def list_reminders(self, status: str = None, user_id: int = None) -> list | None:
        params = {}
        if status:
            params["status"] = status
        if user_id is not None:
            params["user_id"] = user_id
        return self._get("/api/reminders/list", **params)

    def snooze_reminder(self, reminder_id: int, duration: str = "10m") -> dict | None:
        return self._post(f"/api/reminders/{reminder_id}/snooze", json={"duration": duration})

    def dismiss_reminder(self, reminder_id: int) -> dict | None:
        return self._post(f"/api/reminders/{reminder_id}/dismiss")

    def lookup_user(self, channel: str, identifier: str) -> dict | None:
        return self._get("/api/users/lookup", channel=channel, identifier=identifier)

    # ── Telegram relay rules ───────────────────────────────────────────────────

    def get_relay_rules(self) -> list | None:
        return self._get("/api/telegram_relay/rules")

    def set_relay_rule_enabled(self, rule_id: int, enabled: bool) -> dict | None:
        try:
            resp = requests.patch(
                f"{self._base_url}/api/telegram_relay/rules/{rule_id}/enabled",
                json={"enabled": enabled},
                headers=self._headers(),
                timeout=(5, 15),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Orchestrator API error: PATCH /api/telegram_relay/rules/%s/enabled", rule_id)
            return None

    def set_relay_preset(self, enabled: bool) -> dict | None:
        try:
            resp = requests.patch(
                f"{self._base_url}/api/telegram_relay/rules/preset/enabled",
                json={"enabled": enabled},
                headers=self._headers(),
                timeout=(5, 15),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Orchestrator API error: PATCH /api/telegram_relay/rules/preset/enabled")
            return None

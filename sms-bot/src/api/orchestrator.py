import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ORCHESTRATOR_API_URL = os.environ.get("ORCHESTRATOR_API_URL", "http://orchestrator:6000")


class OrchestratorClient:
    def __init__(self, base_url: str = ORCHESTRATOR_API_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def _get(self, path: str, **params) -> dict | list | None:
        try:
            resp = requests.get(f"{self._base_url}{path}", params=params, timeout=(5, 15))
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Orchestrator API error: GET %s", path)
            return None

    def _post(self, path: str, json: dict | None = None) -> dict | None:
        try:
            resp = requests.post(f"{self._base_url}{path}", json=json or {}, timeout=(5, 15))
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Orchestrator API error: POST %s", path)
            return None

    # ── Reminders ────────────────────────────────────────────

    def create_reminder(self, title: str, due_at: str, message: str = None,
                        recurrence: str = None, recipient_ids: list[int] = None,
                        created_by: str = "sms") -> dict | None:
        payload = {
            "title": title,
            "due_at": due_at,
            "message": message,
            "recurrence": recurrence,
            "recipient_ids": recipient_ids,
            "created_by": created_by,
        }
        return self._post("/api/reminders/", json=payload)

    def list_reminders(self, status: str = None) -> list | None:
        params = {}
        if status:
            params["status"] = status
        return self._get("/api/reminders/list", **params)

    def snooze_reminder(self, reminder_id: int, duration: str = "10m") -> dict | None:
        return self._post(f"/api/reminders/{reminder_id}/snooze", json={"duration": duration})

    def dismiss_reminder(self, reminder_id: int) -> dict | None:
        return self._post(f"/api/reminders/{reminder_id}/dismiss")

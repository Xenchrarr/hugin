import logging
import os
from typing import Optional

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError

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
        except RequestsConnectionError as e:
            logger.warning("Orchestrator unreachable: GET %s — %s", path, e)
            return None
        except Exception:
            logger.exception("Orchestrator API error: GET %s", path)
            return None

    def _post(self, path: str, json: dict | None = None) -> dict | None:
        try:
            resp = requests.post(f"{self._base_url}{path}", json=json or {}, timeout=(5, 15))
            resp.raise_for_status()
            return resp.json()
        except RequestsConnectionError as e:
            logger.warning("Orchestrator unreachable: POST %s — %s", path, e)
            return None
        except Exception:
            logger.exception("Orchestrator API error: POST %s", path)
            return None

    def create_reminder(self, title: str, due_at: str, message: str = None,
                        recurrence: str = None, recipient_ids: list[int] = None,
                        user_id: int = None, created_by: str = "telegram") -> dict | None:
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

    def update_notification_setting(self, channel: str, enabled: bool, config: dict,
                                     user_label: str = "", user_id: int = None) -> dict | None:
        return self._post("/api/reminders/notification-settings", json={
            "channel": channel,
            "enabled": enabled,
            "config": config,
            "user_label": user_label,
            "user_id": user_id,
        })

    def register_bot_commands(self, channel: str, commands: list[str]) -> None:
        self._post("/api/bot-commands/register", json={"channel": channel, "commands": commands})

    def lookup_user(self, channel: str, identifier: str) -> dict | None:
        return self._get("/api/users/lookup", channel=channel, identifier=identifier)

    def get_user_by_name(self, name: str) -> dict | None:
        return self._get("/api/users/lookup_by_name", name=name)

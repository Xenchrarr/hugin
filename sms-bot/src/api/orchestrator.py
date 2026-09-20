import base64
import json
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

    def _delete(self, path: str) -> bool:
        try:
            resp = requests.delete(f"{self._base_url}{path}", headers=self._headers(), timeout=(5, 15))
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Orchestrator API error: DELETE %s", path)
            return False

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

    # ── Calendar ──────────────────────────────────────────────

    def get_agenda(self, days: int = 7) -> list[dict] | None:
        data = self._get("/api/ical_sources/agenda", days=days)
        if data is None:
            return None
        return data.get("events")

    # ── Users ─────────────────────────────────────────────────

    def lookup_user(self, channel: str, identifier: str) -> dict | None:
        return self._get("/api/users/lookup", channel=channel, identifier=identifier)

    def patch_user_config(self, user_id: int, values: dict) -> dict | None:
        return self._post(f"/api/users/{user_id}/service-config", json=values)

    def get_service_status(self, status_item: str) -> bool | None:
        data = self._get("/api/connection_status/status", status_item=status_item)
        if not isinstance(data, dict):
            return None
        return bool(data.get("status"))

    # ── Jobs and daily briefing ─────────────────────────────

    def list_jobs(self) -> list[dict] | None:
        data = self._get("/api/jobs/list")
        return data if isinstance(data, list) else None

    def start_job(self, job: dict, run_by: str = "sms") -> dict | None:
        payload = dict(job)
        payload["run_by"] = run_by
        return self._post("/api/jobs/start", json=payload)

    def configure_brief(self, user_id: int, phone: str, time_hhmm: str | None) -> bool:
        jobs = self.list_jobs()
        if jobs is None:
            return False
        name = f"SMS brief {user_id}"
        existing = next((job for job in jobs if job.get("name") == name), None)
        if time_hhmm is None:
            return True if existing is None else self._delete(f"/api/jobs/{existing['id']}")

        hour, minute = (int(part) for part in time_hhmm.split(":", 1))
        payload = {
            "id": existing.get("id", 0) if existing else 0,
            "name": name,
            "enabled": True,
            "job_type": "sms_brief",
            "hour": hour,
            "minute": minute,
            "trigger": "daily",
            "param": json.dumps({"user_id": user_id, "phone": phone}),
            "weekday": "",
            "description": "Compact daily SMS briefing",
            "grouping_value": "sms",
        }
        return self._post("/api/jobs/", json=payload) is not None

    # ── Check-ins ───────────────────────────────────────────

    def create_checkin(self, user_id: int, phone: str, minutes: int) -> dict | None:
        return self._post("/api/checkins/", json={
            "user_id": user_id,
            "phone": phone,
            "minutes": minutes,
        })

    def acknowledge_checkin(self, user_id: int) -> dict | None:
        return self._post("/api/checkins/ack", json={"user_id": user_id})

    # ── Stored SMS inbox ─────────────────────────────────────

    # ── Generic Message Hub inbox ────────────────────────────

    def get_message_hub_inbox_summary(self, phone: str) -> dict | None:
        return self._get(
            "/api/message-hub/inbox/summary",
            recipient_key=f"sms:{phone}",
        )

    def prepare_message_hub_inbox(
        self,
        phone: str,
        source_type: str | None = None,
        source_label: str | None = None,
        limit: int = 5,
    ) -> dict | None:
        return self._post("/api/message-hub/inbox/prepare", json={
            "recipient_key": f"sms:{phone}",
            "source_type": source_type,
            "source_label": source_label,
            "limit": limit,
        })

    def acknowledge_message_hub_inbox(
        self, phone: str, delivery_ids: list[int]
    ) -> bool:
        result = self._post("/api/message-hub/inbox/ack", json={
            "recipient_key": f"sms:{phone}",
            "delivery_ids": delivery_ids,
        })
        return result is not None

    def queue_sms_response(
        self,
        phone: str,
        message: str,
        idempotency_key: str,
        *,
        source_type: str = "sms-command",
        source_label: str = "SMS command",
        acknowledge_delivery_ids: list[int] | None = None,
        ttl_seconds: int = 15 * 60,
    ) -> dict | None:
        delivery = {
            "gateway_key": "sms-main",
            "address": {"phone": phone},
            "recovery_policy": "replay",
            "priority": 80,
            "max_attempts": 8,
            "idempotency_key": idempotency_key,
        }
        if acknowledge_delivery_ids:
            delivery["acknowledge_delivery_ids"] = acknowledge_delivery_ids
        return self._post("/api/message-hub/messages", json={
            "direction": "outbound",
            "kind": "text",
            "source_gateway_key": "sms-main",
            "conversation_key": phone,
            "payload": {"text": message},
            "metadata": {
                "source_type": source_type,
                "source_label": source_label,
            },
            "priority": 80,
            "ttl_seconds": ttl_seconds,
            "idempotency_key": idempotency_key,
            "deliveries": [delivery],
        })

    def queue_mms_response(
        self,
        phone: str,
        message: str,
        image_bytes: bytes,
        image_mime: str,
        idempotency_key: str,
        *,
        source_type: str = "sms-command",
        source_label: str = "SMS command",
        acknowledge_delivery_ids: list[int] | None = None,
        ttl_seconds: int = 15 * 60,
    ) -> dict | None:
        delivery = {
            "gateway_key": "sms-main",
            "address": {"phone": phone},
            "recovery_policy": "replay",
            "priority": 80,
            "max_attempts": 8,
            "idempotency_key": idempotency_key,
        }
        if acknowledge_delivery_ids:
            delivery["acknowledge_delivery_ids"] = acknowledge_delivery_ids
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
        }.get(image_mime.lower(), "bin")
        return self._post("/api/message-hub/messages", json={
            "direction": "outbound",
            "kind": "mms",
            "source_gateway_key": "sms-main",
            "conversation_key": phone,
            "payload": {"text": message},
            "metadata": {
                "source_type": source_type,
                "source_label": source_label,
            },
            "priority": 80,
            "ttl_seconds": ttl_seconds,
            "idempotency_key": idempotency_key,
            "attachments": [{
                "content_type": image_mime,
                "filename": f"image.{extension}",
                "data_base64": base64.b64encode(image_bytes).decode("ascii"),
            }],
            "deliveries": [delivery],
        })

    # ── Telegram relay rules ───────────────────────────────────────────────────

    def get_message_routes(self) -> list | None:
        return self._get("/api/telegram_relay/routes")

    def set_message_route_enabled(self, route_key: str, enabled: bool) -> dict | None:
        try:
            resp = requests.patch(
                f"{self._base_url}/api/telegram_relay/routes/{route_key}/enabled",
                json={"enabled": enabled},
                headers=self._headers(),
                timeout=(5, 15),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception(
                "Orchestrator API error: PATCH /api/telegram_relay/routes/%s/enabled",
                route_key,
            )
            return None

    def set_relay_preset(self, enabled: bool) -> dict | None:
        try:
            resp = requests.patch(
                f"{self._base_url}/api/telegram_relay/routes/preset/enabled",
                json={"enabled": enabled},
                headers=self._headers(),
                timeout=(5, 15),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Orchestrator API error: PATCH /api/telegram_relay/routes/preset/enabled")
            return None

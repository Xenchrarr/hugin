from __future__ import annotations

from datetime import datetime, time
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, g, request

from src.auth import require_auth_or_service_key
from src.models.orchestrator.Alarm import Alarm
from src.persistence.AlarmStorage import AlarmStorage
from src.services.core.alarm_service import AlarmService
from src.services.external.call_service import voice_health

alarm_blueprint = Blueprint("alarms", __name__)


def _identity() -> tuple[int, bool]:
    payload = getattr(g, "jwt_payload", None)
    if payload:
        return int(payload["sub"]), bool(payload.get("is_admin"))
    return 0, True


def _owned(alarm_id: int) -> Alarm | None:
    alarm = AlarmStorage().get(alarm_id)
    payload = getattr(g, "jwt_payload", None)
    if payload:
        user_id, admin = _identity()
        return alarm if alarm and (admin or alarm.user_id == user_id) else None
    # Internal bots authenticate with the shared service key, but still scope
    # alarm operations to the Hugin user they resolved from the sender.
    data = request.get_json(silent=True) or {}
    service_user_id = request.args.get("user_id", type=int) or data.get("user_id")
    return alarm if alarm and service_user_id and alarm.user_id == int(service_user_id) else None


def _from_json(data: dict, existing: Alarm | None = None) -> Alarm:
    user_id, admin = _identity()
    target_user = int(data.get("user_id", existing.user_id if existing else user_id))
    if target_user != user_id and not admin:
        raise ValueError("Cannot create alarms for another user")
    schedule_type = str(data.get("schedule_type", existing.schedule_type if existing else "once"))
    if schedule_type not in {"once", "daily", "weekdays"}:
        raise ValueError("schedule_type must be once, daily, or weekdays")
    timezone_name = str(data.get("timezone", existing.timezone if existing else "Europe/Oslo"))
    alarm_timezone = ZoneInfo(timezone_name)
    scheduled_at = data.get("scheduled_at", existing.scheduled_at if existing else None)
    if isinstance(scheduled_at, str) and scheduled_at:
        scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    if scheduled_at and scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=alarm_timezone)
    local_value = data.get("local_time", existing.local_time if existing else None)
    if isinstance(local_value, str) and local_value:
        local_value = time.fromisoformat(local_value)
    weekdays = data.get("weekdays", existing.weekdays if existing else None)
    if schedule_type == "weekdays" and not weekdays:
        raise ValueError("Select at least one weekday")
    if schedule_type == "once" and not scheduled_at:
        raise ValueError("scheduled_at is required")
    if schedule_type == "once" and scheduled_at <= datetime.now(dt_timezone.utc):
        raise ValueError("scheduled_at must be in the future")
    if schedule_type != "once" and not local_value:
        raise ValueError("local_time is required")
    if weekdays and any(int(day) < 0 or int(day) > 6 for day in weekdays):
        raise ValueError("weekdays must contain numbers from 0 to 6")
    label = str(data.get("label", existing.label if existing else "Wake up")).strip()[:200]
    if not label:
        raise ValueError("label is required")
    return Alarm(
        id=existing.id if existing else 0, user_id=target_user,
        label=label,
        enabled=bool(data.get("enabled", existing.enabled if existing else True)),
        schedule_type=schedule_type, scheduled_at=scheduled_at if schedule_type == "once" else None,
        local_time=local_value if schedule_type != "once" else None,
        weekdays=[int(day) for day in weekdays] if weekdays else None,
        timezone=timezone_name,
        ring_seconds=max(5, min(int(data.get("ring_seconds", existing.ring_seconds if existing else 20)), 60)),
        max_attempts=max(1, min(int(data.get("max_attempts", existing.max_attempts if existing else 3)), 5)),
        retry_interval_seconds=max(30, min(int(data.get("retry_interval_seconds", existing.retry_interval_seconds if existing else 120)), 3600)),
        sms_fallback=bool(data.get("sms_fallback", existing.sms_fallback if existing else True)),
    )


@alarm_blueprint.route("", methods=["GET"])
@require_auth_or_service_key
def list_alarms():
    user_id, admin = _identity()
    if admin:
        requested_user = request.args.get("user_id", type=int)
        selected_user = None if request.args.get("all") == "true" else (requested_user or 0)
    else:
        selected_user = user_id
    rows = AlarmStorage().list(selected_user)
    return [alarm.to_dict() for alarm in rows]


@alarm_blueprint.route("", methods=["POST"])
@require_auth_or_service_key
def create_alarm():
    try:
        alarm = AlarmStorage().save(_from_json(request.get_json(silent=True) or {}))
        AlarmService.instance().schedule(alarm)
        return alarm.to_dict(), 201
    except (TypeError, ValueError) as exc:
        return {"message": str(exc)}, 400


@alarm_blueprint.route("/<int:alarm_id>", methods=["PUT"])
@require_auth_or_service_key
def update_alarm(alarm_id: int):
    existing = _owned(alarm_id)
    if not existing:
        return {"message": "Alarm not found"}, 404
    try:
        alarm = AlarmStorage().save(_from_json(request.get_json(silent=True) or {}, existing))
        AlarmService.instance().schedule(alarm)
        return alarm.to_dict()
    except (TypeError, ValueError) as exc:
        return {"message": str(exc)}, 400


@alarm_blueprint.route("/<int:alarm_id>", methods=["DELETE"])
@require_auth_or_service_key
def delete_alarm(alarm_id: int):
    if not _owned(alarm_id):
        return {"message": "Alarm not found"}, 404
    AlarmService.instance().unschedule(alarm_id)
    return ({"ok": True}, 200) if AlarmStorage().delete(alarm_id) else ({"message": "Alarm not found"}, 404)


@alarm_blueprint.route("/<int:alarm_id>/<action>", methods=["POST"])
@require_auth_or_service_key
def alarm_action(alarm_id: int, action: str):
    alarm = _owned(alarm_id)
    if not alarm:
        return {"message": "Alarm not found"}, 404
    if action in {"enable", "disable"}:
        alarm.enabled = action == "enable"
        saved = AlarmStorage().save(alarm)
        AlarmService.instance().schedule(saved)
        return saved.to_dict()
    if action == "test" or action == "trigger":
        return AlarmService.instance().trigger(alarm_id, source=action), 202
    if action == "snooze":
        minutes = max(1, min(int((request.get_json(silent=True) or {}).get("minutes", 10)), 1440))
        return AlarmService.instance().snooze(alarm_id, minutes), 202
    return {"message": "Unknown action"}, 404


@alarm_blueprint.route("/<int:alarm_id>/occurrences", methods=["GET"])
@require_auth_or_service_key
def occurrences(alarm_id: int):
    if not _owned(alarm_id):
        return {"message": "Alarm not found"}, 404
    storage = AlarmStorage()
    rows = storage.list_occurrences(alarm_id)
    for row in rows:
        row["attempts"] = storage.list_attempts(row["id"])
    return rows


@alarm_blueprint.route("/occurrences/<int:occurrence_id>/attempts", methods=["GET"])
@require_auth_or_service_key
def attempts(occurrence_id: int):
    occurrence = AlarmStorage().get_occurrence(occurrence_id)
    if not occurrence or not _owned(occurrence["alarm_id"]):
        return {"message": "Occurrence not found"}, 404
    return AlarmStorage().list_attempts(occurrence_id)


@alarm_blueprint.route("/occurrences/<int:occurrence_id>/cancel", methods=["POST"])
@require_auth_or_service_key
def cancel_occurrence(occurrence_id: int):
    occurrence = AlarmStorage().get_occurrence(occurrence_id)
    if not occurrence or not _owned(occurrence["alarm_id"]):
        return {"message": "Occurrence not found"}, 404
    AlarmService.instance().cancel_occurrence(occurrence_id)
    return {"ok": True}


@alarm_blueprint.route("/voice-health", methods=["GET"])
@require_auth_or_service_key
def get_voice_health():
    return voice_health()

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.models.orchestrator.Alarm import Alarm
from src.persistence.AlarmStorage import AlarmStorage
from src.persistence.JobDb import JobDb
from src.persistence.UserStorage import UserStorage
from src.services.core.job_scheduler_service import JobSchedulerService
from src.services.core.message_hub_service import MessageHubService
from src.services.external.call_service import ring_phone

log = logging.getLogger(__name__)
_PREFIX = "alarm_"
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class AlarmService:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.scheduler = JobSchedulerService.instance().scheduler

    def load(self) -> None:
        storage = AlarmStorage()
        for alarm in storage.enabled():
            self.schedule(alarm)
        for occurrence in storage.pending_occurrences():
            if occurrence["status"] == "calling":
                storage.mark_interrupted(occurrence["id"])
                alarm = storage.get(occurrence["alarm_id"])
                user = UserStorage().get_user(alarm.user_id) if alarm else None
                phone = str(user.phone_number or "").strip() if user else ""
                if alarm and phone and occurrence.get("source") != "test":
                    self._fallback(alarm, occurrence["id"], phone, "Call outcome uncertain after restart")
                    self._finish_one_time(alarm)
            elif occurrence["status"] in {"pending", "retrying"}:
                run_at = datetime.now(timezone.utc) + timedelta(seconds=5)
                if occurrence["status"] == "pending":
                    scheduled_for = datetime.fromisoformat(occurrence["scheduled_for"])
                    run_at = max(run_at, scheduled_for)
                self._schedule_attempt(occurrence["id"], run_at)
        log.info("Loaded calling alarms")

    def schedule(self, alarm: Alarm) -> None:
        self.unschedule(alarm.id)
        if not alarm.enabled:
            return
        job_id = f"{_PREFIX}{alarm.id}"
        if alarm.schedule_type == "once":
            self.scheduler.add_job(
                _fire_alarm, "date", run_date=alarm.scheduled_at, id=job_id,
                replace_existing=True, args=[alarm.id], misfire_grace_time=600,
            )
            return
        tz = ZoneInfo(alarm.timezone)
        kwargs = {"hour": alarm.local_time.hour, "minute": alarm.local_time.minute, "timezone": tz}
        if alarm.schedule_type == "weekdays":
            kwargs["day_of_week"] = ",".join(_DAYS[d] for d in sorted(alarm.weekdays or []) if 0 <= d <= 6)
        self.scheduler.add_job(
            _fire_alarm, "cron", id=job_id, replace_existing=True, args=[alarm.id],
            coalesce=True, misfire_grace_time=600, **kwargs,
        )

    def unschedule(self, alarm_id: int) -> None:
        try:
            self.scheduler.remove_job(f"{_PREFIX}{alarm_id}")
        except Exception:
            pass

    def trigger(self, alarm_id: int, when: datetime | None = None, source: str = "manual") -> dict:
        alarm = AlarmStorage().get(alarm_id)
        if not alarm:
            raise ValueError("Alarm not found")
        trigger_at = when or datetime.now(timezone.utc)
        # Scheduled firings use a stable key so scheduler retries cannot create a
        # duplicate occurrence. Manual/test calls retain precision so two tests
        # made in the same second remain distinct.
        scheduled_for = trigger_at.replace(microsecond=0) if source == "scheduled" else trigger_at
        occurrence = AlarmStorage().create_occurrence(alarm_id, scheduled_for, source)
        self._schedule_attempt(occurrence["id"], trigger_at)
        return occurrence

    def snooze(self, alarm_id: int, minutes: int) -> dict:
        return self.trigger(alarm_id, datetime.now(timezone.utc) + timedelta(minutes=minutes), "snooze")

    def cancel_occurrence(self, occurrence_id: int) -> None:
        AlarmStorage().finish_occurrence(occurrence_id, "cancelled")
        try:
            self.scheduler.remove_job(f"{_PREFIX}attempt_{occurrence_id}")
        except Exception:
            pass
        from src.services.external.call_service import cancel_call
        cancel_call()

    def _schedule_attempt(self, occurrence_id: int, when: datetime) -> None:
        self.scheduler.add_job(
            _execute_alarm_attempt, "date", run_date=when,
            id=f"{_PREFIX}attempt_{occurrence_id}", replace_existing=True,
            args=[occurrence_id], misfire_grace_time=600,
        )

    def execute_attempt(self, occurrence_id: int) -> None:
        storage = AlarmStorage()
        occurrence = storage.get_occurrence(occurrence_id)
        if not occurrence or occurrence["status"] in {"acknowledged", "unanswered", "failed", "cancelled", "uncertain"}:
            return
        alarm = storage.get(occurrence["alarm_id"])
        if not alarm:
            storage.finish_occurrence(occurrence_id, "failed")
            return
        user = UserStorage().get_user(alarm.user_id)
        phone = str(user.phone_number or "").strip() if user else ""
        is_test = occurrence.get("source") == "test"
        if not phone:
            storage.finish_occurrence(occurrence_id, "failed")
            return
        if storage.recent_attempt_count(alarm.user_id) >= 10:
            storage.finish_occurrence(occurrence_id, "rate_limited")
            if not is_test:
                self._fallback(alarm, occurrence_id, phone, "Call rate limit reached")
            return

        attempt = storage.start_attempt(occurrence_id)
        try:
            result = ring_phone(phone, alarm.ring_seconds, attempt["attempt_token"])
        except Exception as exc:
            log.exception("Alarm %s call request failed", alarm.id)
            result = {"ok": False, "status": "gateway_error", "uncertain": True, "diagnostics": {"error": str(exc)}}
        status = str(result.get("status") or "unknown")
        uncertain = bool(result.get("uncertain"))
        storage.finish_attempt(attempt["id"], status, uncertain, result.get("diagnostics") or {})

        if status == "answered":
            storage.finish_occurrence(occurrence_id, "acknowledged")
            if not is_test:
                self._finish_one_time(alarm)
            return
        if uncertain:
            storage.finish_occurrence(occurrence_id, "uncertain")
            if not is_test:
                self._fallback(alarm, occurrence_id, phone, "Call outcome uncertain")
                self._finish_one_time(alarm)
            return
        max_attempts = 1 if is_test else alarm.max_attempts
        if attempt["attempt_number"] < max_attempts:
            storage.mark_retrying(occurrence_id)
            delay = 60 if status == "busy" else alarm.retry_interval_seconds
            self._schedule_attempt(occurrence_id, datetime.now(timezone.utc) + timedelta(seconds=delay))
            return
        final = "unanswered" if status in {"ring_timeout", "busy", "rejected", "ended", "no_carrier"} else "failed"
        storage.finish_occurrence(occurrence_id, final)
        if not is_test:
            self._fallback(alarm, occurrence_id, phone, f"Final call result: {status}")
            self._finish_one_time(alarm)

    @staticmethod
    def _finish_one_time(alarm: Alarm) -> None:
        if alarm.schedule_type == "once":
            AlarmStorage().set_enabled(alarm.id, False)

    @staticmethod
    def _fallback(alarm: Alarm, occurrence_id: int, phone: str, reason: str) -> None:
        if not alarm.sms_fallback:
            return
        MessageHubService.instance().submit_sms(
            phone_number=phone,
            message=f"ALARM: {alarm.label}\n{reason}",
            source_type="alarm", source_key=str(occurrence_id), source_label="Calling alarms",
            user_id=alarm.user_id, idempotency_key=f"alarm-fallback:{occurrence_id}",
        )


def _fire_alarm(alarm_id: int) -> None:
    try:
        AlarmService.instance().trigger(alarm_id, source="scheduled")
    finally:
        JobDb.instance().close_connection()


def _execute_alarm_attempt(occurrence_id: int) -> None:
    try:
        AlarmService.instance().execute_attempt(occurrence_id)
    finally:
        JobDb.instance().close_connection()

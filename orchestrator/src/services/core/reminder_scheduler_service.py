from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from src.models.orchestrator.Reminder import Reminder
from src.persistence.ReminderStorage import ReminderStorage
from src.persistence.JobDb import JobDb

log = logging.getLogger(__name__)

_SCHEDULER_TZ = pytz.timezone('Europe/Oslo')
_REMINDER_JOB_PREFIX = 'reminder_'


class ReminderSchedulerService:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        raise Exception('call instance()')

    @classmethod
    def instance(cls) -> ReminderSchedulerService:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    obj = cls.__new__(cls)
                    obj._scheduler = None
                    cls._instance = obj
        return cls._instance

    def init_scheduler(self, scheduler: BackgroundScheduler) -> None:
        """Share the APScheduler instance from JobSchedulerService."""
        self._scheduler = scheduler

    def load_active_reminders(self) -> None:
        """Load all active/snoozed reminders from DB into the scheduler."""
        try:
            storage = ReminderStorage()
            active = storage.get_reminders(status_filter='active')
            snoozed = storage.get_reminders(status_filter='snoozed')

            for reminder in active + snoozed:
                self._schedule(reminder)

            log.info("Loaded %d active reminders into scheduler", len(active) + len(snoozed))
        except Exception:
            log.exception("Failed to load active reminders")
        finally:
            JobDb.instance().close_connection()

    def schedule_reminder(self, reminder: Reminder) -> str:
        """Schedule a reminder and return the scheduler job ID."""
        job_id = self._schedule(reminder)
        return job_id

    def unschedule_reminder(self, reminder: Reminder) -> None:
        """Remove a reminder from the scheduler."""
        job_id = self._job_id(reminder)
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            log.debug("Reminder job %s not found in scheduler", job_id)

    def reschedule_reminder(self, reminder: Reminder) -> str:
        """Remove and re-add a reminder to the scheduler."""
        self.unschedule_reminder(reminder)
        return self._schedule(reminder)

    def snooze_reminder(self, reminder_id: int, duration_minutes: int) -> Reminder:
        """Snooze a reminder by the given duration in minutes."""
        storage = ReminderStorage()
        reminder = storage.get_reminder(reminder_id)
        if reminder is None:
            raise ValueError(f"Reminder not found: {reminder_id}")

        new_due = datetime.now(_SCHEDULER_TZ) + timedelta(minutes=duration_minutes)
        reminder.due_at = new_due
        reminder.status = 'snoozed'

        updated = storage.update_reminder(reminder)
        storage.add_reminder_history(reminder_id, 'snoozed', detail=f"{duration_minutes}m")

        self.reschedule_reminder(updated)
        return updated

    def dismiss_reminder(self, reminder_id: int) -> Reminder:
        """Dismiss a reminder (stop it from firing)."""
        storage = ReminderStorage()
        reminder = storage.get_reminder(reminder_id)
        if reminder is None:
            raise ValueError(f"Reminder not found: {reminder_id}")

        self.unschedule_reminder(reminder)

        reminder.status = 'dismissed'
        updated = storage.update_reminder(reminder)
        storage.add_reminder_history(reminder_id, 'dismissed')
        return updated

    # ── Private ──────────────────────────────────────────────

    def _job_id(self, reminder: Reminder) -> str:
        return f"{_REMINDER_JOB_PREFIX}{reminder.id}"

    def _schedule(self, reminder: Reminder) -> str:
        """Add an APScheduler job for the given reminder."""
        job_id = self._job_id(reminder)

        if not reminder.recurrence:
            # One-time reminder: fire at due_at
            self._scheduler.add_job(
                _fire_reminder,
                'date',
                run_date=reminder.due_at,
                id=job_id,
                replace_existing=True,
                args=[reminder.id],
                timezone=_SCHEDULER_TZ,
            )
        elif reminder.recurrence == 'daily':
            due = reminder.due_at
            if hasattr(due, 'astimezone'):
                due = due.astimezone(_SCHEDULER_TZ)
            self._scheduler.add_job(
                _fire_reminder,
                'cron',
                hour=due.hour,
                minute=due.minute,
                id=job_id,
                replace_existing=True,
                args=[reminder.id],
                timezone=_SCHEDULER_TZ,
            )
        elif reminder.recurrence.startswith('weekly:'):
            day_of_week = reminder.recurrence.split(':', 1)[1]
            due = reminder.due_at
            if hasattr(due, 'astimezone'):
                due = due.astimezone(_SCHEDULER_TZ)
            self._scheduler.add_job(
                _fire_reminder,
                'cron',
                day_of_week=day_of_week,
                hour=due.hour,
                minute=due.minute,
                id=job_id,
                replace_existing=True,
                args=[reminder.id],
                timezone=_SCHEDULER_TZ,
            )
        elif reminder.recurrence.startswith('interval:'):
            interval_str = reminder.recurrence.split(':', 1)[1]
            minutes = _parse_interval_minutes(interval_str)
            self._scheduler.add_job(
                _fire_reminder,
                'interval',
                minutes=minutes,
                id=job_id,
                replace_existing=True,
                args=[reminder.id],
                timezone=_SCHEDULER_TZ,
            )
        else:
            log.warning("Unknown recurrence format: %s", reminder.recurrence)
            return job_id

        log.info("Scheduled reminder %s (job_id=%s, recurrence=%s)", reminder.id, job_id, reminder.recurrence)
        return job_id


def _fire_reminder(reminder_id: int) -> None:
    """Callback fired by APScheduler when a reminder is due."""
    from src.services.external.notification_dispatch_service import dispatch_reminder

    try:
        storage = ReminderStorage()
        reminder = storage.get_reminder(reminder_id)

        if reminder is None:
            log.warning("Reminder %s not found at fire time", reminder_id)
            return

        if reminder.status not in ('active', 'snoozed'):
            log.info("Reminder %s has status '%s', skipping", reminder_id, reminder.status)
            return

        success = dispatch_reminder(reminder)

        if not reminder.recurrence:
            # One-time: mark completed or failed
            reminder.status = 'completed' if success else 'failed'
            storage.update_reminder(reminder)
            log.info("One-time reminder %s %s", reminder_id, reminder.status)
        else:
            # Recurring: reset to active (if snoozed)
            if reminder.status == 'snoozed':
                reminder.status = 'active'
                storage.update_reminder(reminder)

    except Exception:
        log.exception("Error firing reminder %s", reminder_id)
    finally:
        JobDb.instance().close_connection()


def _parse_interval_minutes(interval_str: str) -> int:
    """Parse interval strings like '30m', '2h', '1d' into minutes."""
    interval_str = interval_str.strip().lower()
    if interval_str.endswith('m'):
        return int(interval_str[:-1])
    elif interval_str.endswith('h'):
        return int(interval_str[:-1]) * 60
    elif interval_str.endswith('d'):
        return int(interval_str[:-1]) * 1440
    else:
        return int(interval_str)

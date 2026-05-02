from __future__ import annotations

import json
from typing import Optional

from src.models.orchestrator.Reminder import Reminder, NotificationSetting, ReminderHistory
from src.persistence.JobDb import JobDb
from src.persistence.Database import read_sql_file


class ReminderStorage:

    def __init__(self):
        self._db = JobDb.instance()

    def execute(self, query: str, params=None):
        self._last_cursor = self._db.execute(query, params)

    def fetchall(self):
        return self._last_cursor.fetchall()

    def fetchone(self):
        return self._last_cursor.fetchone()

    def commit(self):
        self._db.commit()

    # ── Reminders ────────────────────────────────────────────

    def get_reminders(self, status_filter: Optional[str] = None, user_id: Optional[int] = None) -> list[Reminder]:
        query = read_sql_file('orchestrator/reminder/get_reminders.sql')

        conditions = []
        params = []
        if status_filter:
            conditions.append("r.status = %s")
            params.append(status_filter)
        if user_id is not None:
            conditions.append("r.user_id = %s")
            params.append(user_id)

        if conditions:
            query += "\nWHERE " + " AND ".join(conditions)
        query += "\nORDER BY r.due_at ASC"

        self.execute(query, params if params else None)
        return [Reminder.from_db_row(row) for row in self.fetchall()]

    def get_reminder(self, reminder_id: int) -> Optional[Reminder]:
        query = read_sql_file('orchestrator/reminder/get_reminder.sql')
        self.execute(query, (reminder_id,))
        row = self.fetchone()
        if not row:
            return None
        return Reminder.from_db_row(row)

    def create_reminder(self, reminder: Reminder) -> Reminder:
        query = read_sql_file('orchestrator/reminder/create_reminder.sql')
        self.execute(
            query,
            (
                reminder.title,
                reminder.message,
                reminder.due_at,
                reminder.recurrence,
                reminder.status,
                reminder.recipient_ids,
                reminder.created_by,
                reminder.scheduler_job_id,
                reminder.user_id,
            ),
        )
        row = self.fetchone()
        self.commit()
        return Reminder.from_db_row(row)

    def update_reminder(self, reminder: Reminder) -> Optional[Reminder]:
        query = read_sql_file('orchestrator/reminder/update_reminder.sql')
        self.execute(
            query,
            (
                reminder.title,
                reminder.message,
                reminder.due_at,
                reminder.recurrence,
                reminder.status,
                reminder.recipient_ids,
                reminder.scheduler_job_id,
                reminder.user_id,
                reminder.id,
            ),
        )
        row = self.fetchone()
        self.commit()
        if not row:
            return None
        return Reminder.from_db_row(row)

    def delete_reminder(self, reminder_id: int) -> None:
        query = read_sql_file('orchestrator/reminder/delete_reminder.sql')
        self.execute(query, (reminder_id,))
        self.commit()

    # ── Notification Settings ────────────────────────────────

    def get_notification_settings(self) -> list[NotificationSetting]:
        query = read_sql_file('orchestrator/reminder/get_notification_settings.sql')
        self.execute(query)
        return [NotificationSetting.from_db_row(row) for row in self.fetchall()]

    def upsert_notification_setting(self, setting: NotificationSetting) -> NotificationSetting:
        query = read_sql_file('orchestrator/reminder/upsert_notification_setting.sql')
        config_json = json.dumps(setting.config) if isinstance(setting.config, dict) else setting.config
        self.execute(query, (setting.channel, setting.enabled, config_json, setting.user_label, setting.user_id))
        row = self.fetchone()
        self.commit()
        return NotificationSetting.from_db_row(row)

    def get_notification_settings_for_user(self, user_id: int) -> list[NotificationSetting]:
        query = read_sql_file('orchestrator/reminder/get_notification_settings_by_user.sql')
        self.execute(query, (user_id,))
        return [NotificationSetting.from_db_row(row) for row in self.fetchall()]

    def delete_notification_setting(self, setting_id: int) -> bool:
        query = read_sql_file('orchestrator/reminder/delete_notification_setting.sql')
        self.execute(query, (setting_id,))
        row = self.fetchone()
        self.commit()
        return row is not None

    # ── Reminder History ─────────────────────────────────────

    def add_reminder_history(self, reminder_id: int, action: str, channel: str = None, detail: str = None) -> None:
        query = read_sql_file('orchestrator/reminder/add_reminder_history.sql')
        self.execute(query, (reminder_id, action, channel, detail))
        self.commit()

    def get_reminder_history(self, reminder_id: int) -> list[ReminderHistory]:
        query = read_sql_file('orchestrator/reminder/get_reminder_history.sql')
        self.execute(query, (reminder_id,))
        return [ReminderHistory.from_db_row(row) for row in self.fetchall()]

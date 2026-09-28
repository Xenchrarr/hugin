from __future__ import annotations

import json
from datetime import datetime

from src.models.orchestrator.Alarm import Alarm
from src.persistence.JobDb import JobDb


_COLUMNS = "id,user_id,label,enabled,schedule_type,scheduled_at,local_time,weekdays,timezone,ring_seconds,max_attempts,retry_interval_seconds,sms_fallback,created_at,updated_at"


class AlarmStorage:
    def __init__(self):
        self.db = JobDb.instance()

    def list(self, user_id: int | None = None) -> list[Alarm]:
        sql = f"SELECT {_COLUMNS} FROM alarms"
        params = None
        if user_id is not None:
            sql += " WHERE user_id=%s"
            params = (user_id,)
        rows = self.db.execute(sql + " ORDER BY created_at DESC", params).fetchall()
        return [Alarm.from_row(row) for row in rows]

    def enabled(self) -> list[Alarm]:
        rows = self.db.execute(f"SELECT {_COLUMNS} FROM alarms WHERE enabled ORDER BY id").fetchall()
        return [Alarm.from_row(row) for row in rows]

    def get(self, alarm_id: int) -> Alarm | None:
        row = self.db.execute(f"SELECT {_COLUMNS} FROM alarms WHERE id=%s", (alarm_id,)).fetchone()
        return Alarm.from_row(row) if row else None

    def save(self, alarm: Alarm) -> Alarm:
        values = (alarm.user_id, alarm.label, alarm.enabled, alarm.schedule_type, alarm.scheduled_at,
                  alarm.local_time, alarm.weekdays, alarm.timezone, alarm.ring_seconds,
                  alarm.max_attempts, alarm.retry_interval_seconds, alarm.sms_fallback)
        if alarm.id:
            row = self.db.execute(
                f"UPDATE alarms SET user_id=%s,label=%s,enabled=%s,schedule_type=%s,scheduled_at=%s,local_time=%s,weekdays=%s,timezone=%s,ring_seconds=%s,max_attempts=%s,retry_interval_seconds=%s,sms_fallback=%s,updated_at=NOW() WHERE id=%s RETURNING {_COLUMNS}",
                (*values, alarm.id),
            ).fetchone()
        else:
            row = self.db.execute(
                f"INSERT INTO alarms (user_id,label,enabled,schedule_type,scheduled_at,local_time,weekdays,timezone,ring_seconds,max_attempts,retry_interval_seconds,sms_fallback) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING {_COLUMNS}", values
            ).fetchone()
        self.db.commit()
        return Alarm.from_row(row)

    def delete(self, alarm_id: int) -> bool:
        row = self.db.execute("DELETE FROM alarms WHERE id=%s RETURNING id", (alarm_id,)).fetchone()
        self.db.commit()
        return bool(row)

    def set_enabled(self, alarm_id: int, enabled: bool) -> None:
        self.db.execute("UPDATE alarms SET enabled=%s,updated_at=NOW() WHERE id=%s", (enabled, alarm_id))
        self.db.commit()

    def create_occurrence(self, alarm_id: int, scheduled_for: datetime, source: str = "scheduled") -> dict:
        row = self.db.execute(
            "INSERT INTO alarm_occurrences (alarm_id,scheduled_for,source) VALUES (%s,%s,%s) ON CONFLICT (alarm_id,scheduled_for) DO UPDATE SET alarm_id=EXCLUDED.alarm_id RETURNING id,alarm_id,scheduled_for,source,status,attempt_count,acknowledged_at,completed_at,created_at",
            (alarm_id, scheduled_for, source),
        ).fetchone()
        self.db.commit()
        return self._occurrence(row)

    def get_occurrence(self, occurrence_id: int) -> dict | None:
        row = self.db.execute("SELECT id,alarm_id,scheduled_for,source,status,attempt_count,acknowledged_at,completed_at,created_at FROM alarm_occurrences WHERE id=%s", (occurrence_id,)).fetchone()
        return self._occurrence(row) if row else None

    def list_occurrences(self, alarm_id: int) -> list[dict]:
        rows = self.db.execute("SELECT id,alarm_id,scheduled_for,source,status,attempt_count,acknowledged_at,completed_at,created_at FROM alarm_occurrences WHERE alarm_id=%s ORDER BY scheduled_for DESC LIMIT 100", (alarm_id,)).fetchall()
        return [self._occurrence(row) for row in rows]

    def pending_occurrences(self) -> list[dict]:
        rows = self.db.execute("SELECT id,alarm_id,scheduled_for,source,status,attempt_count,acknowledged_at,completed_at,created_at FROM alarm_occurrences WHERE status IN ('pending','retrying','calling') ORDER BY scheduled_for").fetchall()
        return [self._occurrence(row) for row in rows]

    def start_attempt(self, occurrence_id: int) -> dict:
        occurrence = self.get_occurrence(occurrence_id)
        number = int(occurrence["attempt_count"]) + 1
        token = f"alarm-{occurrence_id}-{number}"
        row = self.db.execute(
            "INSERT INTO alarm_attempts (occurrence_id,attempt_number,attempt_token) VALUES (%s,%s,%s) ON CONFLICT (occurrence_id,attempt_number) DO UPDATE SET attempt_token=alarm_attempts.attempt_token RETURNING id,occurrence_id,attempt_number,attempt_token,status,uncertain,diagnostics,started_at,completed_at",
            (occurrence_id, number, token),
        ).fetchone()
        self.db.execute("UPDATE alarm_occurrences SET status='calling',attempt_count=%s WHERE id=%s", (number, occurrence_id))
        self.db.commit()
        return self._attempt(row)

    def recent_attempt_count(self, user_id: int, hours: int = 1) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) FROM alarm_attempts aa JOIN alarm_occurrences ao ON ao.id=aa.occurrence_id JOIN alarms a ON a.id=ao.alarm_id WHERE a.user_id=%s AND aa.started_at > NOW() - (%s * INTERVAL '1 hour')",
            (user_id, hours),
        ).fetchone()
        return int(row[0])

    def finish_attempt(self, attempt_id: int, status: str, uncertain: bool, diagnostics: dict) -> None:
        self.db.execute("UPDATE alarm_attempts SET status=%s,uncertain=%s,diagnostics=%s,completed_at=NOW() WHERE id=%s", (status, uncertain, json.dumps(diagnostics or {}), attempt_id))
        self.db.commit()

    def finish_occurrence(self, occurrence_id: int, status: str) -> None:
        acknowledged = datetime.now().astimezone() if status == "acknowledged" else None
        self.db.execute("UPDATE alarm_occurrences SET status=%s,acknowledged_at=%s,completed_at=NOW() WHERE id=%s", (status, acknowledged, occurrence_id))
        self.db.commit()

    def mark_retrying(self, occurrence_id: int) -> None:
        self.db.execute("UPDATE alarm_occurrences SET status='retrying' WHERE id=%s", (occurrence_id,))
        self.db.commit()

    def mark_interrupted(self, occurrence_id: int) -> None:
        diagnostics = json.dumps({"error": "Orchestrator restarted while the call outcome was unknown"})
        self.db.execute(
            "UPDATE alarm_attempts SET status='interrupted',uncertain=TRUE,diagnostics=%s,completed_at=NOW() WHERE occurrence_id=%s AND status='calling'",
            (diagnostics, occurrence_id),
        )
        self.db.execute(
            "UPDATE alarm_occurrences SET status='uncertain',completed_at=NOW() WHERE id=%s",
            (occurrence_id,),
        )
        self.db.commit()

    def list_attempts(self, occurrence_id: int) -> list[dict]:
        rows = self.db.execute("SELECT id,occurrence_id,attempt_number,attempt_token,status,uncertain,diagnostics,started_at,completed_at FROM alarm_attempts WHERE occurrence_id=%s ORDER BY attempt_number", (occurrence_id,)).fetchall()
        return [self._attempt(row) for row in rows]

    @staticmethod
    def _occurrence(row) -> dict:
        keys = ("id","alarm_id","scheduled_for","source","status","attempt_count","acknowledged_at","completed_at","created_at")
        return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in zip(keys, row)}

    @staticmethod
    def _attempt(row) -> dict:
        keys = ("id","occurrence_id","attempt_number","attempt_token","status","uncertain","diagnostics","started_at","completed_at")
        return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in zip(keys, row)}

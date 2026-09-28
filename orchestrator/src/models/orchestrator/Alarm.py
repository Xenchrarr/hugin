from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass
class Alarm:
    id: int
    user_id: int
    label: str
    enabled: bool
    schedule_type: str
    scheduled_at: datetime | None
    local_time: time | None
    weekdays: list[int] | None
    timezone: str
    ring_seconds: int
    max_attempts: int
    retry_interval_seconds: int
    sms_fallback: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row):
        return cls(*row)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "user_id": self.user_id, "label": self.label,
            "enabled": self.enabled, "schedule_type": self.schedule_type,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "local_time": self.local_time.strftime("%H:%M") if self.local_time else None,
            "weekdays": self.weekdays, "timezone": self.timezone,
            "ring_seconds": self.ring_seconds, "max_attempts": self.max_attempts,
            "retry_interval_seconds": self.retry_interval_seconds,
            "sms_fallback": self.sms_fallback,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

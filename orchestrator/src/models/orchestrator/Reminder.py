from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Reminder:
    id: int
    title: str
    message: Optional[str]
    due_at: datetime
    recurrence: Optional[str]
    status: str
    recipient_ids: Optional[list[int]]
    created_by: str
    scheduler_job_id: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "recurrence": self.recurrence,
            "status": self.status,
            "recipient_ids": self.recipient_ids,
            "created_by": self.created_by,
            "scheduler_job_id": self.scheduler_job_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "user_id": self.user_id,
        }

    @staticmethod
    def from_db_row(row) -> Reminder:
        return Reminder(
            id=row[0],
            title=row[1],
            message=row[2],
            due_at=row[3],
            recurrence=row[4],
            status=row[5],
            recipient_ids=row[6],
            created_by=row[7],
            scheduler_job_id=row[8],
            created_at=row[9],
            updated_at=row[10],
            user_id=row[11] if len(row) > 11 else None,
        )

    @staticmethod
    def from_dict(obj: dict) -> Reminder:
        return Reminder(
            id=obj.get("id", 0),
            title=obj.get("title", ""),
            message=obj.get("message"),
            due_at=obj.get("due_at"),
            recurrence=obj.get("recurrence"),
            status=obj.get("status", "active"),
            recipient_ids=obj.get("recipient_ids"),
            created_by=obj.get("created_by", "frontend"),
            scheduler_job_id=obj.get("scheduler_job_id"),
            created_at=obj.get("created_at"),
            updated_at=obj.get("updated_at"),
            user_id=obj.get("user_id"),
        )


@dataclass
class NotificationSetting:
    id: int
    channel: str
    enabled: bool
    config: dict
    user_label: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "channel": self.channel,
            "enabled": self.enabled,
            "config": self.config,
            "user_label": self.user_label,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_db_row(row) -> NotificationSetting:
        return NotificationSetting(
            id=row[0],
            channel=row[1],
            enabled=row[2],
            config=row[3],
            user_label=row[4],
            created_at=row[5],
            updated_at=row[6],
            user_id=row[7] if len(row) > 7 else None,
        )

    @staticmethod
    def from_dict(obj: dict) -> NotificationSetting:
        return NotificationSetting(
            id=obj.get("id", 0),
            channel=obj.get("channel", ""),
            enabled=obj.get("enabled", True),
            config=obj.get("config", {}),
            user_label=obj.get("user_label", ""),
            user_id=obj.get("user_id"),
        )


@dataclass
class ReminderHistory:
    id: int
    reminder_id: int
    action: str
    channel: Optional[str]
    detail: Optional[str]
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reminder_id": self.reminder_id,
            "action": self.action,
            "channel": self.channel,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def from_db_row(row) -> ReminderHistory:
        return ReminderHistory(
            id=row[0],
            reminder_id=row[1],
            action=row[2],
            channel=row[3],
            detail=row[4],
            created_at=row[5],
        )

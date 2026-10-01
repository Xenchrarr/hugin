from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WorkflowStepRun:
    id: uuid.UUID | str
    job_run_id: uuid.UUID | str
    step_key: str
    step_type: str
    attempt: int
    status: str
    resolved_input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    error: dict = field(default_factory=dict)
    summary: str = ""
    started_at: datetime | str | None = None
    completed_at: datetime | str | None = None
    heartbeat_at: datetime | str | None = None

    @staticmethod
    def _time(value):
        return value.isoformat() if isinstance(value, datetime) else value

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "job_run_id": str(self.job_run_id),
            "step_key": self.step_key,
            "step_type": self.step_type,
            "attempt": self.attempt,
            "status": self.status,
            "resolved_input": self.resolved_input,
            "output": self.output,
            "error": self.error,
            "summary": self.summary,
            "started_at": self._time(self.started_at),
            "completed_at": self._time(self.completed_at),
            "heartbeat_at": self._time(self.heartbeat_at),
        }

    @classmethod
    def from_db_row(cls, row) -> "WorkflowStepRun":
        return cls(*row[:13])


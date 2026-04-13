from __future__ import annotations

import uuid
from typing import Any


class LogFromLogController:
    def __init__(
        self,
        job_run_id: uuid.UUID | str | None,
        log_text: str,
        severity: str,
        stack_trace: str = '',
    ):
        self.job_run_id = job_run_id
        self.log_text = log_text
        self.severity = severity
        self.stack_trace = stack_trace

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> "LogFromLogController":
        raw_job_run_id = obj.get("job_run_id")

        return LogFromLogController(
            raw_job_run_id,
            obj.get("log_text", ""),
            obj.get("severity", ""),
            obj.get("stack_trace", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_run_id": str(self.job_run_id),
            "log_text": self.log_text,
            "severity": self.severity,
            "stack_trace": self.stack_trace,
        }
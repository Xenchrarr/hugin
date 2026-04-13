from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class LogLevel(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


@dataclass
class JobLog:
    id: int
    job_run_id: int
    log_level: LogLevel
    created_at: str
    message: str
    stack_trace: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id,
            "job_run_id": self.job_run_id,
            "log_level": self.log_level,
            "created_at": self.created_at,
            "message": self.message,
            "stack_trace": self.stack_trace,
        }

    @staticmethod
    def _dt(value: Optional[datetime]):
        return value.isoformat() if value else None

    @staticmethod
    def from_db_row(row) -> "JobLog":
        return JobLog(
            id=row[0],
            job_run_id=row[1],
            log_level=LogLevel(row[2]),
            created_at=row[3],
            message=row[4],
            stack_trace=row[5],
        )
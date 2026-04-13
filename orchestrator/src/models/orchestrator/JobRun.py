from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class JobRun:
    id: uuid.UUID | str
    name: str
    start_time: str
    end_time: Optional[str]
    status: str
    job_type: str
    result: str
    job_id: int
    parameter: str = ""
    run_by: str = ""
    run_by_group: str = "system"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id) if self.id is not None else None,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "job_type": self.job_type,
            "job_id": self.job_id,
            "result": self.result,
            "parameter": self.parameter,
            "run_by": self.run_by,
            "run_by_group": self.run_by_group,
            "metadata": self.metadata,
        }

    @staticmethod
    def from_db_row(row) -> "JobRun":
        return JobRun(
            id=row[0],
            name=row[1],
            start_time=row[2],
            end_time=row[3],
            status=row[4],
            job_type=row[5],
            result=row[6],
            job_id=row[7],
            parameter=row[8],
            run_by=row[9] if len(row) > 9 and row[9] else "",
            run_by_group=row[10] if len(row) > 10 and row[10] else "system",
            metadata=row[11] if len(row) > 11 and row[11] else {},
        )
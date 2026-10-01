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
    job_id: Optional[int]
    parameter: str = ""
    run_by: str = ""
    run_by_group: str = "system"
    metadata: dict = field(default_factory=dict)
    workflow_version: Optional[int] = None
    workflow_input: dict = field(default_factory=dict)
    workflow_definition: dict = field(default_factory=dict)
    last_activity_at: Optional[str] = None

    def to_dict(self, *, include_workflow_definition: bool = False) -> dict:
        result = {
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
            "workflow_version": self.workflow_version,
            "workflow_input": self.workflow_input,
            "last_activity_at": self.last_activity_at,
        }
        if include_workflow_definition and self.workflow_definition:
            result["workflow_definition"] = self.workflow_definition
        return result

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
            workflow_version=row[12] if len(row) > 12 else None,
            workflow_input=row[13] if len(row) > 13 and row[13] else {},
            workflow_definition=row[14] if len(row) > 14 and row[14] else {},
            last_activity_at=row[15] if len(row) > 15 else None,
        )

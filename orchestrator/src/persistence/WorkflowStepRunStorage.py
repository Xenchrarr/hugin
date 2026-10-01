from __future__ import annotations

import json
import uuid

from src.models.orchestrator.WorkflowStepRun import WorkflowStepRun
from src.persistence.Database import read_sql_file
from src.persistence.JobDb import JobDb


class WorkflowStepRunStorage:
    def __init__(self):
        self._db = JobDb.instance()

    def create_step_run(self, job_run_id: uuid.UUID | str, step_key: str,
                        step_type: str, resolved_input: dict,
                        attempt: int = 1) -> WorkflowStepRun:
        item = WorkflowStepRun(uuid.uuid4(), job_run_id, step_key, step_type,
                               attempt, "Pending", resolved_input)
        self._db.execute(read_sql_file("orchestrator/workflow_step_run/create.sql"),
                         (item.id, str(job_run_id), step_key, step_type, attempt,
                          json.dumps(resolved_input)))
        self._db.commit()
        return item

    def mark_step_started(self, step_run_id: uuid.UUID | str) -> None:
        self._db.execute(read_sql_file("orchestrator/workflow_step_run/mark_started.sql"),
                         (str(step_run_id),))
        self._db.commit()

    def heartbeat(self, step_run_id: uuid.UUID | str, job_run_id: uuid.UUID | str) -> None:
        self._db.execute(read_sql_file("orchestrator/workflow_step_run/heartbeat.sql"),
                         (str(step_run_id),))
        self._db.commit()

    def finish_step_run(self, step_run_id: uuid.UUID | str, status: str,
                        output: dict, error: dict, summary: str) -> None:
        self._db.execute(read_sql_file("orchestrator/workflow_step_run/finish.sql"),
                         (status, json.dumps(output), json.dumps(error), summary,
                          str(step_run_id)))
        self._db.commit()

    def get_step_runs(self, job_run_id: uuid.UUID | str) -> list[WorkflowStepRun]:
        rows = self._db.execute(read_sql_file("orchestrator/workflow_step_run/list_for_run.sql"),
                                (str(job_run_id),)).fetchall()
        return [WorkflowStepRun.from_db_row(row) for row in rows]

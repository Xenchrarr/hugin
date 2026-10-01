from __future__ import annotations

import uuid
import json
from typing import Any

from src.persistence.JobDb import JobDb
from src.models.orchestrator.Job import Job
from src.models.orchestrator.JobLog import JobLog
from src.models.orchestrator.JobRun import JobRun
from src.models.orchestrator.JobRunFile import JobRunFile
from src.models.orchestrator.RequestLog import RequestLog
from src.persistence.Database import read_sql_file


class JobStorage:

       
    def __init__(self):
        self._job_db = JobDb.instance()

    def execute(self, query: str, params: Any = None) -> Any:
        return self._job_db.execute(query, params)

    def commit(self) -> None:
        self._job_db.commit()

    # JOBS

    def get_jobs(self) -> list[Job]:
        query = read_sql_file('orchestrator/job/get_jobs.sql')
        jobs = self.execute(query).fetchall()

        return [Job.from_db_row(job) for job in jobs]

    def get_enabled_jobs(self) -> list[Job]:
        query = read_sql_file('orchestrator/job/get_enabled_jobs.sql')
        jobs = self.execute(query).fetchall()
        return [Job.from_db_row(job) for job in jobs]

    def get_job(self, job_id: int, *, for_update: bool = False) -> Job | None:
        query = read_sql_file('orchestrator/job/get_job.sql')
        if for_update:
            query = query.rstrip().rstrip(';') + ' FOR UPDATE'
        job = self.execute(query, (job_id,)).fetchone()

        if not job:
            return None

        return Job.from_db_row(job)

    def create_job(self, job: Job) -> int:
        query = read_sql_file('orchestrator/job/create_job.sql')
        row = self.execute(
            query,
            (
                job.name,
                int(job.enabled),
                job.job_type,
                job.hour,
                job.minute,
                job.trigger,
                job.param,
                job.weekday,
                job.description,
                job.grouping_value,
                job.max_concurrent,
                json.dumps(job.workflow_input or {}),
                job.run_at,
                'pending' if job.trigger == 'once_at' else None,
            ),
        ).fetchone()
        self.commit()

        new_id = row[0]
        job.id = new_id
        return new_id

    def update_job(self, job: Job) -> None:
        query = read_sql_file('orchestrator/job/update_job.sql')

        previous = self.get_job(job.id, for_update=True)
        job.once_status = None
        if job.trigger == 'once_at':
            same_schedule = previous and previous.trigger == 'once_at' and previous.run_at == job.run_at
            job.once_status = previous.once_status if same_schedule else 'pending'
            if job.once_status in {'dispatched', 'missed', 'failed'}:
                job.enabled = False

        enabled = Job.get_int_from_bool(job.enabled)

        self.execute(
            query,
            (
                job.name,
                enabled,
                job.job_type,
                job.hour,
                job.minute,
                job.trigger,
                job.param,
                job.weekday,
                job.description,
                job.grouping_value,
                job.max_concurrent,
                json.dumps(job.workflow_input or {}),
                job.run_at,
                job.once_status,
                job.id,
            ),
        )
        self.commit()

    def delete_job(self, job_id: int) -> None:
        # Delete job_logs and request_log for all runs of this job
        self.execute(
            "DELETE FROM job_logs WHERE job_run_id IN (SELECT id FROM job_runs WHERE job_id = %s)",
            (job_id,),
        )
        self.execute(
            "DELETE FROM request_log WHERE job_run_id IN (SELECT id FROM job_runs WHERE job_id = %s)",
            (job_id,),
        )
        # Delete all job_runs for this job
        self.execute("DELETE FROM job_runs WHERE job_id = %s", (job_id,))
        # Delete the job itself
        query = read_sql_file('orchestrator/job/delete_job.sql')
        self.execute(query, (job_id,))
        self.commit()

    # JOB RUNS

    def get_job_runs(
        self,
        page: int,
        page_size: int,
        grouping_values: list[str] | None,
        status_values: list[str] | None,
        run_by_group: str | None = None,
    ) -> list[JobRun]:
        query = read_sql_file('orchestrator/job_run/get_job_runs.sql')

        page = max(page, 1)
        page_size = max(page_size, 1)
        offset = (page - 1) * page_size

        where_clauses = []
        params = []

        if grouping_values:
            where_clauses.append("j.grouping_value = ANY(%s)")
            params.append(grouping_values)

        if status_values:
            where_clauses.append("runs.status = ANY(%s)")
            params.append(status_values)

        if run_by_group:
            where_clauses.append("runs.run_by_group = %s")
            params.append(run_by_group)

        if where_clauses:
            query += "\nWHERE " + " AND ".join(where_clauses)

        query += "\nORDER BY runs.start_time DESC OFFSET %s LIMIT %s"
        params.extend([offset, page_size])

        rows = self.execute(query, tuple(params)).fetchall()

        return [JobRun.from_db_row(row) for row in rows]

    def get_job_run(self, job_run_id: uuid.UUID | str) -> JobRun | None:
        query = read_sql_file('orchestrator/job_run/get_job_run.sql')
        row = self.execute(query, (job_run_id,)).fetchone()

        if not row:
            return None

        return JobRun.from_db_row(row)

    def get_job_run_by_id(self, job_run_id: uuid.UUID | str) -> JobRun | None:
        query = read_sql_file('orchestrator/job_run/get_job_run_by_id.sql')
        row = self.execute(query, (str(job_run_id),)).fetchone()

        if not row:
            return None

        return JobRun.from_db_row(row)

    def create_job_run(self, job_run: JobRun) -> uuid.UUID:
        query = read_sql_file('orchestrator/job_run/create_job_run.sql')
        job_run_id = uuid.UUID(str(job_run.id)) if job_run.id else uuid.uuid4()

        import json as _json
        metadata_value = _json.dumps(job_run.metadata) if job_run.metadata else '{}'

        self.execute(
            query,
            (
                job_run_id,
                job_run.name,
                job_run.status,
                job_run.job_type,
                job_run.result,
                job_run.job_id,
                job_run.parameter,
                job_run.run_by,
                job_run.run_by_group,
                metadata_value,
                job_run.workflow_version,
                _json.dumps(job_run.workflow_input or {}),
                _json.dumps(job_run.workflow_definition or {}),
            ),
        )
        self.commit()

        return job_run_id

    def get_latest_job_run_id_for_job_type(self, job_type: str) -> uuid.UUID | str | None:
        query = read_sql_file('orchestrator/job_run/get_last_inserted_id_in_job_runs.sql')
        row = self.execute(query, (job_type,)).fetchone()

        return row[0] if row else None

    def update_job_run(self, job_run: JobRun) -> None:
        query = read_sql_file('orchestrator/job_run/update_job_run.sql')
        self.execute(
            query,
            (
                job_run.name,
                job_run.status,
                job_run.result,
                job_run.job_id,
                job_run.id,
            ),
        )
        self.commit()

    def count_total_job_runs(
        self,
        grouping_values: list[str] | None,
        status_values: list[str] | None,
        run_by_group: str | None = None,
    ) -> int:
        query = read_sql_file('orchestrator/job_run/count_total_job_runs.sql')

        where_clauses = []
        params = []

        if grouping_values:
            where_clauses.append("j.grouping_value = ANY(%s)")
            params.append(grouping_values)

        if status_values:
            where_clauses.append("runs.status = ANY(%s)")
            params.append(status_values)

        if run_by_group:
            where_clauses.append("runs.run_by_group = %s")
            params.append(run_by_group)

        if where_clauses:
            query += "\nWHERE " + " AND ".join(where_clauses)

        row = self.execute(query, tuple(params)).fetchone()

        return row[0] if row else 0

    def get_job_runs_by_job_type_id(self, job_type_id: int) -> JobRun | None:
        query = read_sql_file('orchestrator/job_run/get_job_runs_by_job_type_id.sql')
        row = self.execute(query, (job_type_id,)).fetchone()

        if not row:
            return None

        return JobRun.from_db_row(row)

    def get_stale_job_runs(self, stale_after_minutes: int) -> list[JobRun]:
        query = read_sql_file('orchestrator/job_run/get_stale_job_runs.sql')
        rows = self.execute(query, (stale_after_minutes,)).fetchall()

        return [JobRun.from_db_row(row) for row in rows]

    # LOGS

    def get_job_logs_for_job_run(
        self,
        job_run_id: uuid.UUID | str,
        step_run_id: uuid.UUID | str | None = None,
        after_id: int | None = None,
        limit: int | None = None,
    ) -> list[JobLog]:
        query = read_sql_file('orchestrator/log/get_logs_from_job.sql')
        clauses = ['job_run_id = %s']
        params: list[Any] = [job_run_id]
        if step_run_id is not None:
            clauses.append('step_run_id = %s')
            params.append(step_run_id)
        if after_id is not None:
            clauses.append('id > %s')
            params.append(after_id)
        query += '\nWHERE ' + ' AND '.join(clauses) + '\nORDER BY id ASC'
        if limit is not None:
            query += '\nLIMIT %s'
            params.append(limit)
        logs = self.execute(query, tuple(params)).fetchall()
        return [JobLog.from_db_row(log) for log in logs]

    def get_request_logs_for_job_run(
        self,
        job_run_id: uuid.UUID | str,
        page: int,
        page_size: int,
    ) -> list[RequestLog]:
        query = read_sql_file('orchestrator/request_log/get_requests_for_job.sql')

        page = max(page, 1)
        page_size = max(page_size, 1)
        offset = (page - 1) * page_size

        logs = self.execute(query, (job_run_id, offset, page_size)).fetchall()

        return [
            RequestLog(log[0], log[1], log[2], log[3], log[4], log[5], log[6], log[7], log[8], log[9], log[10])
            for log in logs
        ]

    def count_total_request_log_for_run(self, job_run_id: uuid.UUID | str) -> int:
        query = read_sql_file('orchestrator/request_log/count_total_requests_for_job.sql')
        row = self.execute(query, (job_run_id,)).fetchone()

        return row[0] if row else 0

    # FILTER VALUES

    def get_grouping_values(self) -> list[str]:
        query = read_sql_file('orchestrator/job/get_grouping_values.sql')
        rows = self.execute(query).fetchall()

        return [row[0] for row in rows if row[0] is not None]

    def get_status_values(self) -> list[str]:
        query = read_sql_file('orchestrator/job/get_status_values.sql')
        rows = self.execute(query).fetchall()

        return [row[0] for row in rows if row[0] is not None]
    

    def delete_job_run_logs(self, job_run_id: uuid.UUID | str) -> None:
        # Delete logs for the job run
        query = "DELETE FROM job_logs WHERE job_run_id = %s"
        self.execute(query, (job_run_id,))
        self.commit()

    def delete_job_run(self, job_run_id: uuid.UUID | str) -> None:
        # Delete the job run itself
        query = "DELETE FROM job_runs WHERE id = %s"
        self.execute(query, (job_run_id,))
        self.commit()

    def count_running_job_runs_by_job_id(self, job_id: int) -> int:
        row = self.execute(
            read_sql_file('orchestrator/job_run/count_running_job_runs_by_job_id.sql'),
            (job_id,),
        ).fetchone()
        return row[0] if row else 0

    def claim_one_time_job(self, job_id: int, run_at, grace_seconds: int) -> Job | None:
        row = self.execute(
            read_sql_file('orchestrator/job/claim_one_time_job.sql'),
            (grace_seconds, job_id, run_at),
        ).fetchone()
        self.commit()
        return Job.from_db_row(row) if row else None

    def fail_one_time_job(self, job: Job) -> None:
        self.execute(
            "UPDATE jobs SET once_status = 'failed', updated = NOW() "
            "WHERE id = %s AND run_at = %s AND once_status = 'dispatched'",
            (job.id, job.run_at),
        )
        self.commit()

    def create_job_run_file(self, item: JobRunFile) -> None:
        self.execute(
            read_sql_file('orchestrator/job_run_files/create_job_run_file.sql'),
            (
                item.job_run_id,
                item.step_run_id,
                item.original_filename,
                item.storage_path,
                item.download_url,
            ),
        )
        self.commit()

    def get_job_run_files(self, job_run_id: str) -> list[dict]:
        rows = self.execute(
            read_sql_file('orchestrator/job_run_files/get_job_run_files.sql'),
            (job_run_id,),
        ).fetchall()
        return [
            {
                'original_filename': row[0],
                'download_url': row[1],
                'uploaded_at': row[2].isoformat() if row[2] else None,
                'step_run_id': str(row[3]) if row[3] else None,
            }
            for row in rows
        ]

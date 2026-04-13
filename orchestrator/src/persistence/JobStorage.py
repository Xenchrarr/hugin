from __future__ import annotations

import uuid
from typing import Any

from src.persistence.JobDb import JobDb
from src.models.orchestrator.Job import Job
from src.models.orchestrator.JobLog import JobLog
from src.models.orchestrator.JobRun import JobRun
from src.models.orchestrator.RequestLog import RequestLog
from src.persistence.Database import read_sql_file


class JobStorage:

       
    def __init__(self):
        self._job_db = JobDb.instance()

    def execute(self, query: str, params: Any = None) -> None:
        self._last_cursor = self._job_db.execute(query, params)

    def fetchall(self) -> Any:
        return self._last_cursor.fetchall()

    def fetchone(self) -> Any:
        return self._last_cursor.fetchone()

    def commit(self) -> None:
        self._job_db.commit()

    # JOBS

    def get_jobs(self) -> list[Job]:
        query = read_sql_file('orchestrator/job/get_jobs.sql')
        self.execute(query)
        jobs = self.fetchall()

        return [Job.from_db_row(job) for job in jobs]

    def get_enabled_jobs(self) -> list[Job]:
        query = read_sql_file('orchestrator/job/get_enabled_jobs.sql')
        self.execute(query)
        jobs = self.fetchall()

        return [
            Job(
                job[0], job[1], job[2], job[3], job[4], job[5], job[6],
                job[7], job[8], job[9],
                job[10],
                job[11], job[12]
            )
            for job in jobs
        ]

    def get_job(self, job_id: int) -> Job | None:
        query = read_sql_file('orchestrator/job/get_job.sql')
        self.execute(query, (job_id,))
        job = self.fetchone()

        if not job:
            return None

        return Job(
            job[0], job[1], job[2], job[3], job[4], job[5], job[6],
            job[7], job[8], job[9],
           job[10],
            job[11], job[12]
        )

    def create_job(self, job: Job) -> int:
        query = read_sql_file('orchestrator/job/create_job.sql')
        self.execute(
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
            ),
        )

        row = self.fetchone()
        self.commit()

        new_id = row[0]
        job.id = new_id
        return new_id

    def update_job(self, job: Job) -> None:
        query = read_sql_file('orchestrator/job/update_job.sql')

        enabled = Job.get_int_from_bool(job.enabled)

        self.execute(
            query,
            (
                job.name,
                enabled,
                job.hour,
                job.minute,
                job.trigger,
                job.param,
                job.weekday,
                job.description,
                job.grouping_value,
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

        self.execute(query, tuple(params))
        rows = self.fetchall()

        return [JobRun.from_db_row(row) for row in rows]

    def get_job_run(self, job_run_id: uuid.UUID | str) -> JobRun | None:
        query = read_sql_file('orchestrator/job_run/get_job_run.sql')
        self.execute(query, (job_run_id,))
        row = self.fetchone()

        if not row:
            return None

        return JobRun.from_db_row(row)

    def get_job_run_by_id(self, job_run_id: uuid.UUID | str) -> JobRun | None:
        query = read_sql_file('orchestrator/job_run/get_job_run_by_id.sql')
        self.execute(query, (str(job_run_id),))
        row = self.fetchone()

        if not row:
            return None

        return JobRun.from_db_row(row)

    def create_job_run(self, job_run: JobRun) -> uuid.UUID:
        query = read_sql_file('orchestrator/job_run/create_job_run.sql')
        job_run_id = uuid.uuid4()

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
            ),
        )
        self.commit()

        return job_run_id

    def get_latest_job_run_id_for_job_type(self, job_type: str) -> uuid.UUID | str | None:
        query = read_sql_file('orchestrator/job_run/get_last_inserted_id_in_job_runs.sql')
        self.execute(query, (job_type,))
        row = self.fetchone()

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

        self.execute(query, tuple(params))
        row = self.fetchone()

        return row[0] if row else 0

    def get_job_runs_by_job_type_id(self, job_type_id: int) -> JobRun | None:
        query = read_sql_file('orchestrator/job_run/get_job_runs_by_job_type_id.sql')
        self.execute(query, (job_type_id,))
        row = self.fetchone()

        if not row:
            return None

        return JobRun.from_db_row(row)

    def get_stale_job_runs(self, stale_after_minutes: int) -> list[JobRun]:
        query = read_sql_file('orchestrator/job_run/get_stale_job_runs.sql')
        self.execute(query, (stale_after_minutes,))
        rows = self.fetchall()

        return [JobRun.from_db_row(row) for row in rows]

    # LOGS

    def get_job_logs_for_job_run(self, job_run_id: uuid.UUID | str) -> list[JobLog]:
        query = read_sql_file('orchestrator/log/get_logs_from_job.sql')
        self.execute(query, (job_run_id,))
        logs = self.fetchall()

        return [JobLog(log[0], log[1], log[2], log[3], log[4], log[5]) for log in logs]

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

        self.execute(query, (job_run_id, offset, page_size))
        logs = self.fetchall()

        return [
            RequestLog(log[0], log[1], log[2], log[3], log[4], log[5], log[6], log[7], log[8], log[9], log[10])
            for log in logs
        ]

    def count_total_request_log_for_run(self, job_run_id: uuid.UUID | str) -> int:
        query = read_sql_file('orchestrator/request_log/count_total_requests_for_job.sql')
        self.execute(query, (job_run_id,))
        row = self.fetchone()

        return row[0] if row else 0

    # FILTER VALUES

    def get_grouping_values(self) -> list[str]:
        query = read_sql_file('orchestrator/job/get_grouping_values.sql')
        self.execute(query)
        rows = self.fetchall()

        return [row[0] for row in rows if row[0] is not None]

    def get_status_values(self) -> list[str]:
        query = read_sql_file('orchestrator/job/get_status_values.sql')
        self.execute(query)
        rows = self.fetchall()

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

from __future__ import annotations

import logging

from src.api.TeamsBot.TeamsBotMessageSender import send_message
from src.models.orchestrator.JobRun import JobRun
from src.persistence.JobStorage import JobStorage
from src.services.core.job_log_service import get_logs_for_job_run

log = logging.getLogger(__name__)

_job_storage = JobStorage()


def create_job_run(job_run: JobRun):
    try:
        job_run_id = _job_storage.create_job_run(job_run)
        log.info("Job run saved")
        return job_run_id
    except Exception as e:
        log.exception("Failed to save job run")
        send_message(f"Failed to save job run: {e}")
        raise


def update_job_run(job_run: JobRun) -> None:
    _job_storage.update_job_run(job_run)
    log.info("Job run updated")


def get_job_run(job_run_id: str) -> JobRun | None:
    return _job_storage.get_job_run(job_run_id)


def get_job_run_by_id(job_run_id: str) -> JobRun | None:
    return _job_storage.get_job_run_by_id(job_run_id)


def get_job_runs(
    page: int,
    page_size: int,
    grouping_values: list[str] | None,
    status_list: list[str] | None,
    run_by_group: str | None = None,
) -> list[JobRun]:
    return _job_storage.get_job_runs(page, page_size, grouping_values, status_list, run_by_group=run_by_group)


def get_total_job_runs(
    grouping_values: list[str] | None,
    status_list: list[str] | None,
    run_by_group: str | None = None,
) -> int:
    return _job_storage.count_total_job_runs(
        grouping_values=grouping_values,
        status_values=status_list,
        run_by_group=run_by_group,
    )

def delete_job_run(job_run_id: str) -> None:

    _job_storage.delete_job_run_logs(job_run_id)
    _job_storage.delete_job_run(job_run_id)
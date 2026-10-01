from src.persistence.JobStorage import JobStorage
from src.models.orchestrator.JobLog import JobLog
from src.models.orchestrator.RequestLog import RequestLog



_job_storage = JobStorage()


def get_logs_for_job_run(job_run_id: str, step_run_id: str | None = None,
                         after_id: int | None = None, limit: int | None = None) -> list[JobLog]:
    return _job_storage.get_job_logs_for_job_run(job_run_id, step_run_id, after_id, limit)


def get_request_log_for_job_run(job_run_id: str, page: int, page_size: int) -> list[RequestLog]:
    return _job_storage.get_request_logs_for_job_run(job_run_id, page, page_size)


def get_total_count_request_log_for_job_run(job_run_id: str) -> int:
    return _job_storage.count_total_request_log_for_run(job_run_id)

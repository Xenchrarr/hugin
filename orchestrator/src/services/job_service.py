from __future__ import annotations

import datetime
import logging
import threading
import traceback
import uuid
from typing import List

log = logging.getLogger(__name__)

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.api.TeamsBot.TeamsBotMessageSender import send_message
from src.models.api.JobForApi import JobForApi
from src.models.orchestrator.Job import Job
from src.models.orchestrator.JobRun import JobRun
from src.persistence.DatabaseLogger import DatabaseLogger
from src.persistence.JobDb import JobDb
from src.persistence.JobStorage import JobStorage
from src.services.job_run_service import create_job_run, get_job_run_by_id, update_job_run
from src.services.job_scheduler_service import JobSchedulerService
from src.services.threading_service import get_value_from_thread, add_value_to_thread, JobCancelledException
from src.services.cancellation_service import register_cancellation_token, cleanup as cleanup_cancellation_token, request_cancellation, is_cancelled

_job_storage = JobStorage()


def get_jobs() -> list[Job]:
    return _job_storage.get_jobs()


def get_enabled_jobs() -> list[Job]:
    return _job_storage.get_enabled_jobs()


def update_job(job: Job) -> Job | None:
    _job_storage.update_job(job)
    JobSchedulerService.instance().modify_job(job)
    return _job_storage.get_job(job.id)


def create_job(job: Job) -> Job:
    new_id = _job_storage.create_job(job)
    created_job = _job_storage.get_job(new_id)

    if created_job is None:
        raise Exception(f"Created job with id {new_id}, but failed to load it afterwards")

    JobSchedulerService.instance().add_job(created_job)
    return created_job

def get_job(job_id: int) -> Job | None:
    return _job_storage.get_job(job_id)


def delete_job(job_id: int) -> None:
    _job_storage.delete_job(job_id)
    JobSchedulerService.instance().reload_all_jobs()


def run_job_once(job: Job, run_by: str = "system", run_by_group: str = "system", metadata: dict | None = None) -> uuid.UUID:
    job.trigger = 'once'
    log.info("Running job once")

    is_running = JobSchedulerService.instance().check_if_job_is_running(job)
    if is_running:
        log.warning("Job is already running")
        raise Exception("Job is already running")

    param = job.param if job.param is not None else '0'
    job_run = JobRun(
        id="",
        name=job.name,
        start_time=datetime.datetime.now(),
        end_time=None,
        status='Started',
        job_type=job.job_type,
        result='',
        job_id=job.id,
        parameter=param,
        run_by=run_by,
        run_by_group=run_by_group,
        metadata=metadata or {},
    )
    job_run_id = create_job_run(job_run)

    JobSchedulerService.instance().add_job_for_running_once(job, job_run_id=job_run_id)
    return job_run_id


def get_grouping_values() -> List[str]:
    return _job_storage.get_grouping_values()


def get_status_values() -> List[str]:
    return _job_storage.get_status_values()


def cancel_job_run(job_run_id: str) -> None:
    """Cancel a running job by its job_run_id."""
    job_run = get_job_run_by_id(job_run_id)
    if job_run is None:
        raise ValueError(f"Job run not found: {job_run_id}")
    if job_run.status != 'Started':
        raise ValueError(f"Job run is not running (status: {job_run.status})")

    cancelled = request_cancellation(job_run_id)

    if not cancelled:
        # No cancellation token found — the job thread may have already finished
        # or never registered a token. Force-update the DB as a safety net.
        job_run.status = 'Cancelled'
        job_run.result = f"{job_run.name} job was cancelled (force)"
        job_run.end_time = datetime.datetime.now()
        update_job_run(job_run)
        return

    # Start a safety-net timer: if the job thread hasn't updated the status
    # within 30 seconds, force-update it to Cancelled in the DB.
    def _safety_net():
        run = get_job_run_by_id(job_run_id)
        if run is not None and run.status == 'Started':
            run.status = 'Cancelled'
            run.result = f"{run.name} job was cancelled (timeout)"
            run.end_time = datetime.datetime.now()
            update_job_run(run)

    timer = threading.Timer(30.0, _safety_net)
    timer.daemon = True
    timer.start()


def get_running_jobs_from_scheduler() -> list[JobForApi]:
    scheduler_jobs = JobSchedulerService.instance().get_jobs_for_api()
    jobs = get_enabled_jobs()

    to_return = []

    for scheduled_job in scheduler_jobs:
        base_job_id = str(scheduled_job.job_id).replace("_once", "")

        matching_job = next(
            (job for job in jobs if str(job.id) == base_job_id),
            None
        )

        if matching_job:
            scheduled_job.name = matching_job.name

        to_return.append(scheduled_job)

    return to_return


def run_job(job: Job, job_function, job_run_id=None):

    log.info("%s job started", job.name)
    param = '0'
    if job.param is not None:
        param = job.param
    job_run = JobRun(
        id="",
        name=job.name,
        start_time=datetime.datetime.now().isoformat(),
        end_time=None,
        status='Started',
        job_type=job.job_type,
        result='',
        job_id=job.id,
        parameter=param,
        run_by="system",
    )

    try:
        if job_run_id is None:
            job_run_id = create_job_run(job_run)
            log.info("%s job run created", job.name)
        else:
            log.info("%s using pre-created job run %s", job.name, job_run_id)

        thread_local = ThreadLocalSingleton.instance().thread_local

        job_run.id = job_run_id
        thread_local.job_run_id = job_run_id

        # Register cancellation token and store in thread-local for check_cancellation()
        cancellation_event = register_cancellation_token(str(job_run_id))
        thread_local.cancellation_event = cancellation_event

        logger = DatabaseLogger()

        try:
            logger.log_info(f"Running {job.name} job | job_id: {job.id}")
            logger.log_info(f"Param: {param}")
            job_function['function'](param)
        except JobCancelledException:
            job_run.status = 'Cancelled'
            job_run.result = f"{job.name} job was cancelled"
            job_run.end_time = datetime.datetime.now().isoformat()
            logger.log_info(f"{job.name} job was cancelled by user")
            update_job_run(job_run)
            return
        except Exception as e:
            job_run.status = 'Error'
            error_message = str(e)
            job_run.result = f"Error running {job.name} job: {error_message}"
            job_run.end_time = datetime.datetime.now().isoformat()
            stack_trace = traceback.format_exception(e)
            stack_trace_string = '\n'.join(stack_trace)
            logger.log_error(f"Error running {job.name} job: {error_message}", stack_trace_string)
            update_job_run(job_run)
            send_message(f"Error running {job.name} job: {error_message[:30]}")
            return

        thread_job_status = get_value_from_thread('job_status')
        job_run.status = thread_job_status if thread_job_status else 'Finished'

        add_value_to_thread('job_status', None)
        job_run.result = f"{job.name} job run finished"
        job_run.end_time = datetime.datetime.now().isoformat()
        update_job_run(job_run)
    finally:
        # Clean up cancellation token
        if job_run_id is not None:
            cleanup_cancellation_token(str(job_run_id))
        # Always return the DB connection to the pool after a background job completes.
        JobDb.instance().close_connection()
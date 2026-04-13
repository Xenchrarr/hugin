from datetime import datetime
import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)

_SCHEDULER_TZ = pytz.timezone('Europe/Oslo')

from src.jobs_registry import jobs_registry
from src.models.api.JobForApi import JobForApi
from src.models.orchestrator.Job import Job
from src.persistence.JobStorage import JobStorage
from src.persistence.JobDb import JobDb

import src.jobs  # noqa: F401 — imported for side-effect: registers @job_type decorators


def get_job_func(job: Job, job_run_id=None):
    from src.services.core.job_service import run_job
    job_function = jobs_registry.get(job.job_type)
    if job_function is None:
        raise Exception(f"No job function registered for job type: {job.job_type}")
    return lambda: run_job(job=job, job_function=job_function, job_run_id=job_run_id)


def get_trigger(job: Job):
    if job.trigger == 'daily':
        return 'cron'
    if job.trigger == 'interval':
        return 'interval'
    if job.trigger == 'once':
        return 'date'
    if job.trigger == 'weekly':
        return 'cron'
    return None


class JobSchedulerService:
    scheduler = None
    _instance = None

    def __init__(self):
        raise Exception('call instance()')

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.scheduler = BackgroundScheduler(
                daemon=True,
                timezone=_SCHEDULER_TZ,
            )
        return cls._instance

    def start_scheduler(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def stop_scheduler(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def remove_all_jobs(self):
        log.info("Removing all jobs")
        self.scheduler.remove_all_jobs()

    def pause_all_jobs(self):
        if self.scheduler.running:
            self.scheduler.pause()

    def resume_all_jobs(self):
        if self.scheduler.running:
            self.scheduler.resume()

    def modify_job(self, job: Job):
        try:
            self.remove_job(job)
        except Exception as e:
            log.warning("Error removing job: %s", e)

        self.add_job(job)
        log.info("Modified job %s, id: %s", job.name, job.id)

    def remove_job(self, job: Job):
        self.scheduler.remove_job(str(job.id))

    def start_all_jobs(self):
        log.info("Starting all jobs")
        try:
            job_storage = JobStorage()
            jobs = job_storage.get_enabled_jobs()

            for job in jobs:
                self.add_job(job)

            self._register_stale_job_reaper()

            self.start_scheduler()
        except Exception as e:
            log.exception("Error starting all jobs")
        finally:
            JobDb.instance().close_connection()

    def reload_all_jobs(self):
        if not self.scheduler.running:
            log.warning("job_scheduler_service instance NOT running")
            return

        log.info("Reloading all jobs")
        self.remove_all_jobs()
        self.start_all_jobs()

    def _register_stale_job_reaper(self):
        from src.services.core.stale_job_reaper import reap_stale_job_runs

        self.scheduler.add_job(
            reap_stale_job_runs,
            'interval',
            minutes=5,
            id='__stale_job_reaper',
            replace_existing=True,
        )
        log.info("Registered stale job reaper (runs every 5 minutes)")

    def add_job(self, job: Job):
        if not job.enabled:
            return

        job_func = get_job_func(job)
        trigger = get_trigger(job)

        if trigger is None:
            raise Exception(f"Unsupported trigger type: {job.trigger}")

        log.info("Adding job %s with trigger %s | hour: %s, minute: %s", job.name, job.trigger, job.hour, job.minute)

        if job.trigger == 'interval':
            self.scheduler.add_job(
                job_func,
                trigger,
                hours=job.hour,
                minutes=job.minute,
                id=str(job.id),
                replace_existing=True,
            )
        elif job.trigger == 'daily':
            self.scheduler.add_job(
                job_func,
                trigger,
                hour=job.hour,
                minute=job.minute,
                id=str(job.id),
                replace_existing=True,
            )
        elif job.trigger == 'weekly':
            self.scheduler.add_job(
                job_func,
                trigger,
                day_of_week=job.get_int_from_weekday(),
                hour=job.hour,
                minute=job.minute,
                id=str(job.id),
                replace_existing=True,
            )

    def add_job_for_running_once(self, job: Job, job_run_id=None):
        if not self.scheduler.running:
            log.warning("job_scheduler_service instance NOT running")
            raise Exception('Job scheduler service not running')

        job_func = get_job_func(job, job_run_id=job_run_id)
        job_id = f"{job.id}_once"

        log.info("Adding job %s with trigger once | Running now", job.name)

        self.scheduler.add_job(
            job_func,
            'date',
            run_date=datetime.now(_SCHEDULER_TZ),
            id=job_id,
            replace_existing=True,
        )

    def check_if_job_is_running(self, job: Job) -> bool:
        job_storage = JobStorage()
        running_job = job_storage.get_job_runs_by_job_type_id(job.id)

        if running_job is None:
            return False

        return running_job.status == 'Started'

    def get_jobs_for_api(self) -> list[JobForApi]:
        local_tz = pytz.timezone("Europe/Oslo")
        jobs = self.scheduler.get_jobs()

        job_data = []
        for job in jobs:
            next_run = job.next_run_time
            if next_run:
                next_run = next_run.astimezone(local_tz)

            job_data.append(
                JobForApi(
                    job.id,
                    job.name,
                    next_run,
                    job.trigger,
                )
            )

        return job_data
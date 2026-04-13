"""Safety-net reaper that marks job runs stuck in 'Started' as 'Error'.

This catches edge cases where both the HTTP and subprocess timeouts fail to
fire (e.g. container restart, OOM kill, network partition).
"""

from __future__ import annotations

import datetime
import logging
import os

from src.persistence.JobDb import JobDb
from src.persistence.JobStorage import JobStorage
from src.services.job_run_service import update_job_run

log = logging.getLogger(__name__)

# A job run is considered stale if it has been in 'Started' for longer than
# this many minutes.  Default: 20 minutes.
STALE_JOB_THRESHOLD_MINUTES = int(os.environ.get('STALE_JOB_THRESHOLD_MINUTES', '20'))


def reap_stale_job_runs() -> None:
    """Find job runs stuck in 'Started' beyond the threshold and mark them as Error."""
    try:
        storage = JobStorage()
        stale_runs = storage.get_stale_job_runs(STALE_JOB_THRESHOLD_MINUTES)

        for job_run in stale_runs:
            log.warning("Marking stale job run %s (%s) as Error", job_run.id, job_run.name)
            job_run.status = 'Error'
            job_run.result = (
                f"{job_run.name} job timed out – stuck in Started state "
                f"for over {STALE_JOB_THRESHOLD_MINUTES} minutes (reaped by safety net)"
            )
            job_run.end_time = datetime.datetime.now()
            update_job_run(job_run)

        if stale_runs:
            log.info("Reaped %d stale job run(s)", len(stale_runs))
    except Exception as e:
        log.exception("Error during stale job reap")
    finally:
        JobDb.instance().close_connection()

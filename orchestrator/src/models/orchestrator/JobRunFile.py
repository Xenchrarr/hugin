from dataclasses import dataclass


@dataclass(frozen=True)
class JobRunFile:
    job_run_id: str
    original_filename: str
    storage_path: str
    download_url: str
    step_run_id: str | None = None

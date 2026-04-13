from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


FILE_STORAGE_PATH = os.getenv('FILE_STORAGE_PATH', '/data/logs')
FILE_STORAGE_URL = os.getenv('FILE_STORAGE_URL', '/logs')


def upload_file(content: str, directory: str, filename: str) -> str | None:
    """Write content to the shared file storage volume and return the URL served by nginx."""
    try:
        file_dir = Path(FILE_STORAGE_PATH) / directory
        file_dir.mkdir(parents=True, exist_ok=True)

        file_path = file_dir / filename
        file_path.write_text(content, encoding='utf-8')

        url = f"{FILE_STORAGE_URL}/{directory}/{filename}"
        return url
    except Exception as e:
        log.exception("Error writing log file to storage")
        return None


def upload_log_file(content: str, job_run_id: int | str, label: str) -> str | None:
    """Upload a log entry (message or stack_trace) and return the URL."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"{label}_{timestamp}.txt"
    directory = f"job_runs/{job_run_id}"
    return upload_file(content, directory, filename)

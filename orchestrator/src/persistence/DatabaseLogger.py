import logging

from src.persistence.JobDb import JobDb
from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.models.api.LogFromLogController import LogFromLogController
from src.persistence.Database import read_sql_file
from src.services.core.file_storage_service import upload_log_file

log = logging.getLogger(__name__)


class DatabaseLogger:
    def __init__(self):
        self._job_db = JobDb.instance()

    def log_from_api(self, log_object: LogFromLogController) -> None:
        severity = log_object.severity
        message = log_object.log_text
        stack_trace = log_object.stack_trace
        job_run_id = log_object.job_run_id

        if severity == 'ERROR':
            self.log_error(message, stack_trace, job_run_id)
        elif severity == 'WARNING':
            self.log_warning(message, job_run_id)
        elif severity == 'INFO':
            self.log_info(message, job_run_id)
        elif severity == 'DEBUG':
            self.log_debug(message, job_run_id)
        else:
            log.warning("Unknown severity level: %s", severity)

    def log_error(self, message: str, stack_trace: str | None = None, job_run_id=None) -> None:
        self._log('ERROR', message, stack_trace=stack_trace, job_run_id=job_run_id)

    def log_info(self, message: str, job_run_id=None) -> None:
        self._log('INFO', message, job_run_id=job_run_id)

    def log_warning(self, message: str, job_run_id=None) -> None:
        self._log('WARNING', message, job_run_id=job_run_id)

    def log_debug(self, message: str, job_run_id=None) -> None:
        self._log('DEBUG', message, job_run_id=job_run_id)

    def _log(self, level: str, message: str, stack_trace: str | None = "", job_run_id=None) -> None:
        thread_local = ThreadLocalSingleton.instance().thread_local
        query = read_sql_file('orchestrator/log/create_log.sql')

        if job_run_id is None:
            job_run_id = getattr(thread_local, 'job_run_id', None)

        # print(message)
        safe_message = self._truncate_or_upload(message, 2000, job_run_id, f'{level}_message')
        trace = self._truncate_or_upload(stack_trace, 2000, job_run_id, f'{level}_stack_trace')
        log.debug("%s", safe_message)
        self._job_db.run_query(query, (job_run_id, level, safe_message, trace))

    @staticmethod
    def _truncate_or_upload(text: str | None, max_length: int, job_run_id, label: str) -> str | None:
        if not text:
            return text
        if len(text) <= max_length:
            return text

        url = upload_log_file(text, job_run_id, label)
        if url is None:
            return text[:max_length]
        return url
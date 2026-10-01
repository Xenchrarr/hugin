import os
import queue
import threading
import time

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.api.orchestrator.orchestrator_logger import send_log_batch
from src.models.LogFromLogController import LogFromLogController
from src.services import should_log

_BATCH_SIZE = max(1, int(os.environ.get('LOG_BATCH_SIZE', '50')))
_FLUSH_INTERVAL = max(0.1, float(os.environ.get('LOG_FLUSH_INTERVAL', '2')))
_queue: queue.Queue = queue.Queue()


def _send_with_retry(payloads):
    error = None
    for attempt in range(4):
        if attempt:
            time.sleep(2 ** (attempt - 1))
        try:
            send_log_batch(payloads)
            return
        except Exception as exc:
            error = exc
    print(f'[log] dropping {len(payloads)} entries after retries: {error}', flush=True)


class _Flusher(threading.Thread):
    def run(self):
        while True:
            try:
                batch = [_queue.get(timeout=_FLUSH_INTERVAL)]
            except queue.Empty:
                continue
            while len(batch) < _BATCH_SIZE:
                try:
                    batch.append(_queue.get_nowait())
                except queue.Empty:
                    break
            try:
                _send_with_retry([item.to_dict() for item in batch])
            finally:
                for _ in batch:
                    _queue.task_done()


_Flusher(daemon=True, name='log-flusher').start()


def flush_all(timeout=30):
    deadline = time.monotonic() + timeout
    with _queue.all_tasks_done:
        while _queue.unfinished_tasks:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _queue.all_tasks_done.wait(timeout=min(remaining, 1))
    return True


def _write_log(message, severity, stack_trace='', job_run_id=None, step_run_id=None):
    if not should_log:
        return
    local = ThreadLocalSingleton.instance().thread_local
    job_run_id = job_run_id or getattr(local, 'job_run_id', 0)
    step_run_id = step_run_id or getattr(local, 'step_run_id', None)
    _queue.put(LogFromLogController(job_run_id, message, severity, stack_trace, step_run_id))


def log_info(message, job_run_id=None, step_run_id=None):
    _write_log(message, 'INFO', job_run_id=job_run_id, step_run_id=step_run_id)


def log_error(message, stack_trace='', job_run_id=None, step_run_id=None):
    _write_log(message, 'ERROR', stack_trace, job_run_id, step_run_id)


def log_warning(message, job_run_id=None, step_run_id=None):
    _write_log(message, 'WARNING', job_run_id=job_run_id, step_run_id=step_run_id)


def log_debug(message, job_run_id=None, step_run_id=None):
    _write_log(message, 'DEBUG', job_run_id=job_run_id, step_run_id=step_run_id)

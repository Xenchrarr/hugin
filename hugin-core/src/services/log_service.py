
from concurrent.futures import ThreadPoolExecutor

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.api.orchestrator.orchestrator_logger import send_log_message
from src.models.LogFromLogController import LogFromLogController

from src.services import should_log

_executor = ThreadPoolExecutor(max_workers=5)


def _non_blocking_send(log):
    try:
        send_log_message(log.to_dict())

    except Exception as e:
        print(e)

def _write_log(message, severity, stack_trace:str = '', job_run_id=None):
    if not should_log:
        return
    thread_local = ThreadLocalSingleton.instance().thread_local


    if job_run_id is None:
        job_run_id = getattr(thread_local, 'job_run_id', 0)
    log = LogFromLogController(log_text=message, severity=severity, job_run_id=job_run_id, stack_trace=stack_trace)

    _executor.submit(_non_blocking_send, log)



def log_info(message, job_run_id=None):
    _write_log(message, 'INFO', job_run_id=job_run_id)

def log_error(message:str, stack_trace: str, job_run_id=None):
    _write_log(message, 'ERROR', stack_trace=stack_trace, job_run_id=job_run_id)

def log_warning(message:str, job_run_id=None):
    _write_log(message, 'WARNING', job_run_id=job_run_id)

def log_debug(message:str, job_run_id=None):
    _write_log(message, 'DEBUG', job_run_id=job_run_id)

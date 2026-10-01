import threading
from dataclasses import dataclass, field


def workflow_step_callback_id(step_run_id: str) -> str:
    if not step_run_id:
        raise ValueError('step_run_id is required')
    return f'step:{step_run_id}'


def job_run_callback_id(job_run_id: str) -> str:
    if not job_run_id:
        raise ValueError('job_run_id is required')
    return f'job:{job_run_id}'


@dataclass
class _Entry:
    event: threading.Event = field(default_factory=threading.Event)
    status: str | None = None
    result: dict = field(default_factory=dict)
    message: str = ''


class CallbackRegistry:
    def __init__(self):
        self.entries = {}
        self.lock = threading.Lock()

    def register(self, key):
        with self.lock:
            if key in self.entries:
                raise ValueError(f'Callback already registered: {key}')
            self.entries[key] = _Entry()

    def signal(self, key, status, result, message=''):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return False
            if entry.event.is_set():
                return True
            entry.status, entry.result, entry.message = status, result, message
            entry.event.set()
            return True

    def wait(self, key, timeout):
        with self.lock:
            entry = self.entries.get(key)
        if entry is None:
            raise KeyError(f'Callback not registered: {key}')
        if not entry.event.wait(timeout):
            raise TimeoutError(f'Callback timed out after {int(timeout)}s')
        return entry.status, entry.result, entry.message

    def cleanup(self, key):
        with self.lock:
            self.entries.pop(key, None)


callback_registry = CallbackRegistry()

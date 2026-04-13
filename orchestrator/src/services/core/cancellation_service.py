import threading

# Registry mapping job_run_id (str) → threading.Event
_cancellation_tokens: dict[str, threading.Event] = {}
_lock = threading.Lock()


def register_cancellation_token(job_run_id: str) -> threading.Event:
    """Register a cancellation token for a job run. Called when a job starts."""
    event = threading.Event()
    with _lock:
        _cancellation_tokens[str(job_run_id)] = event
    return event


def request_cancellation(job_run_id: str) -> bool:
    """Request cancellation of a running job. Returns True if a token was found and set."""
    with _lock:
        event = _cancellation_tokens.get(str(job_run_id))
    if event is not None:
        event.set()
        return True
    return False


def is_cancelled(job_run_id: str) -> bool:
    """Check if cancellation has been requested for a job run."""
    with _lock:
        event = _cancellation_tokens.get(str(job_run_id))
    return event is not None and event.is_set()


def cleanup(job_run_id: str) -> None:
    """Remove the cancellation token for a completed/cancelled job run."""
    with _lock:
        _cancellation_tokens.pop(str(job_run_id), None)

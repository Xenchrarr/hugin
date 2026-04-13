from src.ThreadLocalSingleton import ThreadLocalSingleton


class JobCancelledException(Exception):
    """Raised when a running job is cancelled by user request."""
    pass


def add_value_to_thread(key: str, value: str):

    thread_local = ThreadLocalSingleton.instance().thread_local
    thread_local.__setattr__(key, value)

def get_value_from_thread(key: str):

    try:
        thread_local = ThreadLocalSingleton.instance().thread_local
        return thread_local.__getattribute__(key)
    except Exception as e:
        return None


def check_cancellation():
    """Check if the current job has been cancelled. Call this between significant steps in a job function.
    Raises JobCancelledException if cancellation was requested."""
    thread_local = ThreadLocalSingleton.instance().thread_local
    cancellation_event = getattr(thread_local, 'cancellation_event', None)
    if cancellation_event is not None and cancellation_event.is_set():
        raise JobCancelledException("Job was cancelled by user request")
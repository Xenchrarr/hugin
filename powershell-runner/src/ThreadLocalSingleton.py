import threading


class ThreadLocalSingleton:
    _instance = None
    _thread_local_storage = threading.local()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def thread_local(self):
        return self._thread_local_storage

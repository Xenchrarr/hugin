import logging
import threading
from contextlib import contextmanager
from typing import Any

from src.persistence.Database import DatabasePool
from . import JOB_DB_USER_NAME, JOB_DB_PASSWORD, JOB_DB_HOST, JOB_DB_PORT, JOB_DB


class JobDb:
    _instance = None
    _instance_lock = threading.Lock()
    _thread_local = threading.local()

    def __init__(self):
        raise Exception("call instance()")

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    obj = cls.__new__(cls)
                    DatabasePool.init(
                        host=JOB_DB_HOST,
                        port=int(JOB_DB_PORT),
                        database=JOB_DB,
                        user=JOB_DB_USER_NAME,
                        password=JOB_DB_PASSWORD,
                    )
                    cls._instance = obj
        return cls._instance

    # ------------------------------------------------------------------
    # Thread-local connection management
    # Each thread borrows one connection from the pool on first use.
    # The connection MUST be returned via close_connection().
    # ------------------------------------------------------------------

    def get_connection(self):
        """Return the thread-local pooled connection, borrowing one if needed."""
        conn = getattr(self._thread_local, "conn", None)
        if conn is None or conn.closed:
            self._thread_local.conn = DatabasePool.instance().getconn()
        return self._thread_local.conn

    def close_connection(self, commit: bool = True) -> None:
        """Return the thread-local connection to the pool."""
        conn = getattr(self._thread_local, "conn", None)
        if conn is not None:
            try:
                if not conn.closed:
                    if commit:
                        conn.commit()
                    else:
                        conn.rollback()
            except Exception:
                logging.debug("Error finalizing connection before returning to pool", exc_info=True)
            finally:
                try:
                    DatabasePool.instance().putconn(conn)
                except Exception:
                    logging.debug("Error returning connection to pool", exc_info=True)
                self._thread_local.conn = None

    @contextmanager
    def connection(self):
        """Context manager that guarantees the connection is returned to the pool."""
        try:
            yield self.get_connection()
        finally:
            self.close_connection()

    # ------------------------------------------------------------------
    # Convenience query helpers
    # ------------------------------------------------------------------

    def execute(self, query: str, params: Any = None):
        conn = self.get_connection()
        cur = conn.execute(query, params)
        return cur

    def fetchall(self, cursor=None):
        if cursor is not None:
            return cursor.fetchall()
        return self.get_connection().execute("SELECT 0").fetchall()

    def fetchone(self, cursor=None):
        if cursor is not None:
            return cursor.fetchone()
        return self.get_connection().execute("SELECT 0").fetchone()

    def commit(self) -> None:
        conn = getattr(self._thread_local, "conn", None)
        if conn and not conn.closed:
            conn.commit()

    def rollback(self) -> None:
        conn = getattr(self._thread_local, "conn", None)
        if conn and not conn.closed:
            conn.rollback()

    def run_query(self, query: str, params: Any = None) -> None:
        conn = self.get_connection()
        try:
            conn.execute(query, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            logging.getLogger(__name__).exception("Error running query")
            raise
import logging
import os
from contextlib import contextmanager
from typing import Any, Iterable, Optional

from psycopg_pool import ConnectionPool


def _load_psycopg():
    try:
        import psycopg
        return psycopg
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support is unavailable because psycopg could not load a pq wrapper. "
            "The application can still start, but database-backed features must remain disabled "
            "until the runtime environment provides a working psycopg/libpq installation."
        ) from exc


class DatabasePool:
    """Application-wide connection pool backed by psycopg_pool.ConnectionPool."""

    _instance: Optional["DatabasePool"] = None

    def __init__(
        self,
        host: str,
        database: str,
        user: str,
        password: str,
        port: int = 5432,
        min_size: int = 2,
        max_size: int = 10,
        timeout: float = 5.0,
    ):
        self._pool = ConnectionPool(
            kwargs={
                "host": host,
                "port": port,
                "dbname": database,
                "user": user,
                "password": password,
                "connect_timeout": int(timeout),
            },
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            open=True,
        )
        logging.info(
            "Connection pool created for %s/%s (min=%d, max=%d)",
            host, database, min_size, max_size,
        )

    @classmethod
    def init(cls, **kwargs) -> "DatabasePool":
        """Create the singleton pool. Safe to call multiple times; only the first call takes effect."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def instance(cls) -> "DatabasePool":
        if cls._instance is None:
            raise RuntimeError("DatabasePool.init() must be called before instance()")
        return cls._instance

    def getconn(self):
        """Borrow a connection from the pool."""
        return self._pool.getconn()

    def putconn(self, conn) -> None:
        """Return a connection to the pool."""
        self._pool.putconn(conn)

    @contextmanager
    def connection(self):
        """Context manager: borrows a connection and guarantees it is returned."""
        conn = self.getconn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            self.putconn(conn)

    def close(self) -> None:
        self._pool.close()

    def get_stats(self) -> dict:
        return self._pool.get_stats()


def find_project_root(start_path: str, root_marker_file: str) -> str:
    current = os.path.abspath(start_path)

    while True:
        if os.path.isfile(os.path.join(current, root_marker_file)):
            return current

        parent = os.path.dirname(current)
        if parent == current:
            raise Exception(
                f"Project root not found. Expected to find {root_marker_file} "
                f"in one of the parent directories of {start_path}."
            )

        current = parent


def read_sql_file(file_name: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = find_project_root(base_dir, 'app.py')
    file_path = os.path.join(project_root, "sql", file_name)

    with open(file_path, "r", encoding="utf-8") as sql_file:
        return sql_file.read()


def run_init_sql() -> None:
    """Run init/init.sql if the 'jobs' table does not yet exist."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = find_project_root(base_dir, 'app.py')
    init_path = os.path.join(project_root, "init", "init.sql")

    if not os.path.isfile(init_path):
        logging.warning("init.sql not found at %s – skipping DB init", init_path)
        return

    pool = DatabasePool.instance()
    with pool.connection() as conn:
        cur = conn.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_name = 'jobs'"
            ")"
        )
        exists = cur.fetchone()[0]
        if exists:
            logging.info("Database tables already exist – skipping init.sql")
            return

        with open(init_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.execute(sql)
        logging.info("init.sql executed successfully")


def run_migrations() -> None:
    """Apply pending SQL migrations from sql/migrations/ in order."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = find_project_root(base_dir, 'app.py')
    migrations_dir = os.path.join(project_root, "sql", "migrations")

    if not os.path.isdir(migrations_dir):
        logging.info("No migrations directory found – skipping")
        return

    pool = DatabasePool.instance()
    with pool.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  filename VARCHAR(255) PRIMARY KEY,"
            "  applied_at TIMESTAMP DEFAULT NOW()"
            ")"
        )

        cur = conn.execute("SELECT filename FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

        migration_files = sorted(
            f for f in os.listdir(migrations_dir)
            if f.endswith('.sql')
        )

        for filename in migration_files:
            if filename in applied:
                continue

            filepath = os.path.join(migrations_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read()

            logging.info("Applying migration: %s", filename)
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (filename,),
            )
            logging.info("Migration applied: %s", filename)

        logging.info("All migrations up to date")


class Database:
    def __init__(
        self,
        host: str,
        database: str,
        user: str,
        password: str,
        port: int = 5432,
        timeout: int = 5,
    ):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.timeout = timeout

        self._conn = None
        self._cursor = None

        self._connect()

    def _connect(self) -> None:
        try:
            psycopg = _load_psycopg()
            self._conn = psycopg.connect(
                host=self.host,
                port=self.port,
                dbname=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=self.timeout,
            )
            self._cursor = self._conn.cursor()
            logging.info(
                "Connected to PostgreSQL %s/%s as %s",
                self.host,
                self.database,
                self.user,
            )
        except Exception:
            logging.exception("Error connecting to PostgreSQL")
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close(commit=exc_type is None)

    @property
    def connection(self):
        return self._conn

    @property
    def cursor(self):
        return self._cursor

    @staticmethod
    def test_connection(host: str, database: str, user: str, password: str, port: int = 5432) -> bool:
        try:
            psycopg = _load_psycopg()
            with psycopg.connect(
                host=host,
                port=port,
                dbname=database,
                user=user,
                password=password,
                connect_timeout=5,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True
        except Exception:
            return False

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> None:
        if params is None:
            self.cursor.execute(sql)
        else:
            self.cursor.execute(sql, params)

    def executemany(self, sql: str, params: Optional[Iterable[Iterable[Any]]] = None) -> None:
        self.cursor.executemany(sql, params or ())

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()

    def query(self, sql: str, params: Optional[Iterable[Any]] = None):
        self.execute(sql, params)
        return self.fetchall()

    def commit(self) -> None:
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()

    def reconnect(self) -> None:
        self.close(commit=False)
        self._connect()

    def close(self, commit: bool = True) -> None:
        try:
            if self.connection and not self.connection.closed:
                if commit:
                    self.connection.commit()
                else:
                    self.connection.rollback()
        finally:
            try:
                if self._cursor and not self._cursor.closed:
                    self._cursor.close()
            finally:
                if self._conn and not self._conn.closed:
                    self._conn.close()

    def is_alive(self) -> bool:
        try:
            if not self.connection or self.connection.closed:
                return False

            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

            return True
        except Exception as e:
            logging.debug("PostgreSQL ping failed: %s", e)
            return False
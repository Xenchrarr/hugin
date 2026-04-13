import logging

from src.persistence import (JOB_DB_USER_NAME, JOB_DB_PASSWORD, JOB_DB_CONNECTION_STRING, JOB_DB_HOST, JOB_DB_PORT, JOB_DB)
from src.persistence.Database import Database

log = logging.getLogger(__name__)


def check_if_connection_to_job_db_is_valid() -> bool:
    try:
        return Database.test_connection(host=JOB_DB_HOST,
                                        database=JOB_DB,
                                        user=JOB_DB_USER_NAME,
                                        password=JOB_DB_PASSWORD,
                                        port=int(JOB_DB_PORT))
    except Exception as e:
        log.exception("Failed to connect to database")
        return False



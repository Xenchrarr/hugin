from src.persistence.JobDb import JobDb
from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.persistence.Database import read_sql_file


class RequestLogger:
    _instance = None

    def __init__(self):
        self._job_db = JobDb.instance()

    def log_request(
        self,
        area: str,
        request_data: str,
        request_type: str,
        response_code: int,
        response_data: str,
        function_name: str,
        api_name: str,
        comment: str | None,
    ) -> None:
        thread_local = ThreadLocalSingleton.instance().thread_local
        query = read_sql_file('orchestrator/request_log/create_request_log.sql')

        job_run_id = getattr(thread_local, 'job_run_id', None)

        response = response_data[:3900] if response_data else None

        self._job_db.run_query(
            query,
            (
                job_run_id,
                area,
                request_data,
                request_type,
                response_code,
                response,
                function_name,
                api_name,
                comment,
            ),
        )
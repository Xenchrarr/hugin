from __future__ import annotations

from src.persistence.JobDb import JobDb
from src.persistence.Database import read_sql_file


class UserCommandPermissionStorage:

    def __init__(self):
        self._db = JobDb.instance()

    def _execute(self, query: str, params=None):
        self._cursor = self._db.execute(query, params)

    def _fetchall(self):
        return self._cursor.fetchall()

    def _commit(self):
        self._db.commit()

    def list_by_user(self, user_id: int) -> list[str]:
        query = read_sql_file("orchestrator/user_command_permission/list_by_user.sql")
        self._execute(query, (user_id,))
        return [row[0] for row in self._fetchall()]

    def add(self, user_id: int, command_path: str) -> None:
        query = read_sql_file("orchestrator/user_command_permission/add.sql")
        self._execute(query, (user_id, command_path))
        self._commit()

    def remove(self, user_id: int, command_path: str) -> None:
        query = read_sql_file("orchestrator/user_command_permission/remove.sql")
        self._execute(query, (user_id, command_path))
        self._commit()

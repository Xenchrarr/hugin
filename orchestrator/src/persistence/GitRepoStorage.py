from __future__ import annotations

from typing import Any

from src.persistence.JobDb import JobDb
from src.models.orchestrator.GitRepo import GitRepo
from src.persistence.Database import read_sql_file


class GitRepoStorage:

    def __init__(self):
        self._db = JobDb.instance()

    def execute(self, query: str, params: Any = None):
        self._last_cursor = self._db.execute(query, params)

    def fetchall(self):
        return self._last_cursor.fetchall()

    def fetchone(self):
        return self._last_cursor.fetchone()

    def commit(self):
        self._db.commit()

    def get_repos(self) -> list[GitRepo]:
        query = read_sql_file('orchestrator/git_repo/get_repos.sql')
        self.execute(query)
        rows = self.fetchall()
        return [GitRepo.from_db_row(row) for row in rows]

    def get_repo(self, repo_id: int) -> GitRepo | None:
        query = read_sql_file('orchestrator/git_repo/get_repo.sql')
        self.execute(query, (repo_id,))
        row = self.fetchone()
        if not row:
            return None
        return GitRepo.from_db_row(row)

    def create_repo(self, repo: GitRepo) -> int:
        query = read_sql_file('orchestrator/git_repo/create_repo.sql')
        enabled = 1 if repo.enabled else 0
        self.execute(query, (repo.name, repo.url, repo.branch, enabled))
        row = self.fetchone()
        self.commit()
        return row[0]

    def update_repo(self, repo: GitRepo) -> None:
        query = read_sql_file('orchestrator/git_repo/update_repo.sql')
        enabled = 1 if repo.enabled else 0
        self.execute(query, (repo.name, repo.url, repo.branch, enabled, repo.id))
        self.commit()

    def delete_repo(self, repo_id: int) -> None:
        query = read_sql_file('orchestrator/git_repo/delete_repo.sql')
        self.execute(query, (repo_id,))
        self.commit()

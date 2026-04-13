from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.persistence.JobDb import JobDb
from src.persistence.Database import read_sql_file


@dataclass
class ScriptPermission:
    id: int
    script_name: str
    allowed_for_servicedesk: bool
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "script_name": self.script_name,
            "allowed_for_servicedesk": self.allowed_for_servicedesk,
            "created": self.created.isoformat() if self.created else None,
            "updated": self.updated.isoformat() if self.updated else None,
        }

    @staticmethod
    def from_db_row(row) -> "ScriptPermission":
        return ScriptPermission(
            id=row[0],
            script_name=row[1],
            allowed_for_servicedesk=row[2],
            created=row[3],
            updated=row[4],
        )


class ScriptPermissionStorage:
    def __init__(self):
        self._db = JobDb.instance()

    def _execute(self, query: str, params=None):
        self._cursor = self._db.execute(query, params)

    def _fetchall(self):
        return self._cursor.fetchall()

    def _fetchone(self):
        return self._cursor.fetchone()

    def _commit(self):
        self._db.commit()

    def get_all(self) -> list[ScriptPermission]:
        query = read_sql_file("orchestrator/script_permission/get_all.sql")
        self._execute(query)
        return [ScriptPermission.from_db_row(row) for row in self._fetchall()]

    def get_allowed_script_names(self) -> list[str]:
        query = read_sql_file("orchestrator/script_permission/get_allowed.sql")
        self._execute(query)
        return [row[0] for row in self._fetchall()]

    def upsert(self, script_name: str, allowed: bool) -> None:
        query = read_sql_file("orchestrator/script_permission/upsert.sql")
        self._execute(query, (script_name, allowed))
        self._commit()

    def delete(self, script_name: str) -> None:
        query = read_sql_file("orchestrator/script_permission/delete.sql")
        self._execute(query, (script_name,))
        self._commit()

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.persistence.JobDb import JobDb
from src.persistence.Database import read_sql_file


@dataclass
class ScriptReasonOption:
    id: int
    script_name: str
    option_label: str
    display_order: int = 0
    created: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "script_name": self.script_name,
            "option_label": self.option_label,
            "display_order": self.display_order,
            "created": self.created.isoformat() if self.created else None,
        }

    @staticmethod
    def from_db_row(row) -> "ScriptReasonOption":
        return ScriptReasonOption(
            id=row[0],
            script_name=row[1],
            option_label=row[2],
            display_order=row[3],
            created=row[4],
        )


class ScriptReasonStorage:
    def __init__(self):
        self._db = JobDb.instance()

    def _execute(self, query: str, params=None):
        self._cursor = self._db.execute(query, params)

    def _fetchall(self):
        return self._cursor.fetchall()

    def _commit(self):
        self._db.commit()

    def get_all(self) -> list[ScriptReasonOption]:
        query = read_sql_file("orchestrator/script_reason/get_all_options.sql")
        self._execute(query)
        return [ScriptReasonOption.from_db_row(row) for row in self._fetchall()]

    def get_all_grouped(self) -> dict[str, list[str]]:
        """Return reason options grouped by script_name: {script_name: [label1, label2, ...]}"""
        options = self.get_all()
        grouped: dict[str, list[str]] = defaultdict(list)
        for opt in options:
            grouped[opt.script_name].append(opt.option_label)
        return dict(grouped)

    def insert(self, script_name: str, option_label: str, display_order: int = 0) -> None:
        query = read_sql_file("orchestrator/script_reason/insert_option.sql")
        self._execute(query, (script_name, option_label, display_order))
        self._commit()

    def update(self, option_id: int, option_label: str, display_order: int) -> None:
        query = read_sql_file("orchestrator/script_reason/update_option.sql")
        self._execute(query, (option_label, display_order, option_id))
        self._commit()

    def delete(self, option_id: int) -> None:
        query = read_sql_file("orchestrator/script_reason/delete_option.sql")
        self._execute(query, (option_id,))
        self._commit()

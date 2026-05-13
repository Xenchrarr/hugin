from __future__ import annotations

from typing import Optional

from src.models.orchestrator.IcalSource import IcalSource
from src.persistence.JobDb import JobDb
from src.persistence.Database import read_sql_file


class IcalSourceStorage:

    def __init__(self):
        self._db = JobDb.instance()

    def execute(self, query: str, params=None):
        self._last_cursor = self._db.execute(query, params)

    def fetchall(self):
        return self._last_cursor.fetchall()

    def fetchone(self):
        return self._last_cursor.fetchone()

    def commit(self):
        self._db.commit()

    def list_sources(self) -> list[IcalSource]:
        query = read_sql_file('orchestrator/ical_source/list_ical_sources.sql')
        self.execute(query)
        return [IcalSource.from_db_row(row) for row in self.fetchall()]

    def list_enabled_sources(self) -> list[IcalSource]:
        query = read_sql_file('orchestrator/ical_source/list_enabled_ical_sources.sql')
        self.execute(query)
        return [IcalSource.from_db_row(row) for row in self.fetchall()]

    def get_source(self, source_id: int) -> Optional[IcalSource]:
        query = read_sql_file('orchestrator/ical_source/get_ical_source.sql')
        self.execute(query, (source_id,))
        row = self.fetchone()
        return IcalSource.from_db_row(row) if row else None

    def create_source(self, source: IcalSource) -> IcalSource:
        query = read_sql_file('orchestrator/ical_source/create_ical_source.sql')
        self.execute(query, (source.name, source.url, 1 if source.enabled else 0, source.color))
        row = self.fetchone()
        self.commit()
        return IcalSource.from_db_row(row)

    def update_source(self, source: IcalSource) -> Optional[IcalSource]:
        query = read_sql_file('orchestrator/ical_source/update_ical_source.sql')
        self.execute(query, (source.name, source.url, 1 if source.enabled else 0, source.color, source.id))
        row = self.fetchone()
        self.commit()
        return IcalSource.from_db_row(row) if row else None

    def delete_source(self, source_id: int) -> None:
        query = read_sql_file('orchestrator/ical_source/delete_ical_source.sql')
        self.execute(query, (source_id,))
        self.commit()

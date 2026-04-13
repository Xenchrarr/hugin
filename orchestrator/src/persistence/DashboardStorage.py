from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.persistence.JobDb import JobDb


class DashboardStorage:

    def __init__(self):
        self._job_db = JobDb.instance()

    def _execute(self, query: str, params=None):
        cursor = self._job_db.execute(query, params)
        return cursor

    def get_total_runs(self, since: Optional[datetime] = None) -> int:
        query = "SELECT COUNT(*) FROM job_runs"
        params = []
        if since:
            query += " WHERE start_time >= %s"
            params.append(since)
        row = self._execute(query, tuple(params)).fetchone()
        return row[0] if row else 0

    def get_runs_by_status(self, since: Optional[datetime] = None) -> list[dict]:
        query = "SELECT status, COUNT(*) AS cnt FROM job_runs"
        params = []
        if since:
            query += " WHERE start_time >= %s"
            params.append(since)
        query += " GROUP BY status ORDER BY cnt DESC"
        rows = self._execute(query, tuple(params)).fetchall()
        return [{"status": r[0], "count": r[1]} for r in rows]

    def get_runs_by_job_type(self, since: Optional[datetime] = None) -> list[dict]:
        query = "SELECT job_type, COUNT(*) AS cnt FROM job_runs"
        params = []
        if since:
            query += " WHERE start_time >= %s"
            params.append(since)
        query += " GROUP BY job_type ORDER BY cnt DESC"
        rows = self._execute(query, tuple(params)).fetchall()
        return [{"job_type": r[0], "count": r[1]} for r in rows]

    def get_top_control_rooms(self, since: Optional[datetime] = None, limit: int = 10) -> list[dict]:
        query = """
            SELECT metadata->>'ControlRoom' AS control_room, COUNT(*) AS cnt
            FROM job_runs
            WHERE metadata->>'ControlRoom' IS NOT NULL
              AND metadata->>'ControlRoom' != ''
        """
        params = []
        if since:
            query += " AND start_time >= %s"
            params.append(since)
        query += " GROUP BY control_room ORDER BY cnt DESC LIMIT %s"
        params.append(limit)
        rows = self._execute(query, tuple(params)).fetchall()
        return [{"control_room": r[0], "count": r[1]} for r in rows]

    def get_recent_runs(self, limit: int = 5) -> list[dict]:
        query = """
            SELECT name, status, end_time, parameter, metadata
            FROM job_runs
            ORDER BY start_time DESC
            LIMIT %s
        """
        rows = self._execute(query, (limit,)).fetchall()
        return [
            {
                "name": r[0],
                "status": r[1],
                "end_time": r[2].isoformat() if r[2] else None,
                "parameter": r[3],
                "metadata": r[4] if r[4] else {},
            }
            for r in rows
        ]

    def get_runs_since(self, since: datetime) -> int:
        query = "SELECT COUNT(*) FROM job_runs WHERE start_time >= %s"
        row = self._execute(query, (since,)).fetchone()
        return row[0] if row else 0

    def get_reason_counts(self, since: Optional[datetime] = None) -> list[dict]:
        query = """
            SELECT
                COALESCE(metadata->'reason'->>'selected', 'Other / free-text') AS reason,
                COUNT(*) AS cnt
            FROM job_runs
            WHERE metadata->'reason' IS NOT NULL
        """
        params = []
        if since:
            query += " AND start_time >= %s"
            params.append(since)
        query += " GROUP BY reason ORDER BY cnt DESC"
        rows = self._execute(query, tuple(params)).fetchall()
        return [{"reason": r[0], "count": r[1]} for r in rows]

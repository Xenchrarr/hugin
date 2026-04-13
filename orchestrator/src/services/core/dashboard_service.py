from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from src.persistence.DashboardStorage import DashboardStorage

_storage = DashboardStorage()

RANGE_MAP = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}


def _parse_since(range_key: str) -> Optional[datetime]:
    delta = RANGE_MAP.get(range_key)
    if delta is None:
        return None
    return datetime.now() - delta


def get_dashboard_stats(range_key: str = "30d") -> dict:
    if range_key not in RANGE_MAP:
        range_key = "30d"

    since = _parse_since(range_key)
    now = datetime.now()

    return {
        "total_runs": _storage.get_total_runs(since=since),
        "runs_last_24h": _storage.get_runs_since(now - timedelta(hours=24)),
        "runs_last_7d": _storage.get_runs_since(now - timedelta(days=7)),
        "runs_last_30d": _storage.get_runs_since(now - timedelta(days=30)),
        "runs_by_status": _storage.get_runs_by_status(since=since),
        "runs_by_job_type": _storage.get_runs_by_job_type(since=since),
        "top_control_rooms": _storage.get_top_control_rooms(since=since),
        "recent_runs": _storage.get_recent_runs(),
        "reason_counts": _storage.get_reason_counts(since=since),
    }

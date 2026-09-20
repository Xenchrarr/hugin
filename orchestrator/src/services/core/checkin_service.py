from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.persistence.JobDb import JobDb
from src.persistence.UserStorage import UserStorage
from src.services.core.job_scheduler_service import JobSchedulerService
from src.services.core.message_hub_service import MessageHubService

log = logging.getLogger(__name__)
_PREFIX = "checkin_"


def create_checkin(user_id: int, phone: str, minutes: int) -> dict:
    user = UserStorage().get_user(user_id)
    if user is None:
        raise ValueError("User not found")
    alert_phone = str((user.config or {}).get("checkin_alert_phone") or "").strip()
    if not alert_phone:
        raise ValueError("Set config.checkin_alert_phone first")
    deadline = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    row = JobDb.instance().execute(
        """
        INSERT INTO checkins (user_id, phone_number, alert_phone, deadline)
        VALUES (%s, %s, %s, %s)
        RETURNING id, user_id, phone_number, alert_phone, deadline, status
        """,
        (user_id, phone, alert_phone, deadline),
    ).fetchone()
    JobDb.instance().commit()
    _schedule(int(row[0]), deadline)
    return _row_dict(row)


def acknowledge_checkin(user_id: int) -> dict | None:
    row = JobDb.instance().execute(
        """
        UPDATE checkins SET status = 'acknowledged', acknowledged_at = NOW()
        WHERE id = (
            SELECT id FROM checkins WHERE user_id = %s AND status = 'active'
            ORDER BY deadline ASC LIMIT 1
        )
        RETURNING id, user_id, phone_number, alert_phone, deadline, status
        """,
        (user_id,),
    ).fetchone()
    JobDb.instance().commit()
    if row:
        try:
            JobSchedulerService.instance().scheduler.remove_job(f"{_PREFIX}{row[0]}")
        except Exception:
            pass
    return _row_dict(row) if row else None


def load_active_checkins() -> None:
    rows = JobDb.instance().execute(
        "SELECT id, deadline FROM checkins WHERE status = 'active' ORDER BY deadline"
    ).fetchall()
    for checkin_id, deadline in rows:
        _schedule(int(checkin_id), deadline)
    log.info("Loaded %d active check-ins", len(rows))


def _schedule(checkin_id: int, deadline) -> None:
    JobSchedulerService.instance().scheduler.add_job(
        _escalate,
        "date",
        run_date=deadline,
        id=f"{_PREFIX}{checkin_id}",
        replace_existing=True,
        args=[checkin_id],
        misfire_grace_time=None,
    )


def _escalate(checkin_id: int) -> None:
    try:
        row = JobDb.instance().execute(
            """
            UPDATE checkins SET status = 'escalated', escalated_at = NOW()
            WHERE id = %s AND status = 'active'
            RETURNING id, user_id, phone_number, alert_phone, deadline, status
            """,
            (checkin_id,),
        ).fetchone()
        JobDb.instance().commit()
        if not row:
            return
        user = UserStorage().get_user(int(row[1]))
        name = (user.display_name or user.username) if user else f"user {row[1]}"
        MessageHubService.instance().submit_sms(
            phone_number=row[3],
            message=f"CHECK-IN ALERT: {name} did not confirm safety by the agreed deadline.",
            source_type="system",
            source_key=str(checkin_id),
            source_label="Check-in alert",
            idempotency_key=f"checkin-alert:{checkin_id}",
        )
    finally:
        JobDb.instance().close_connection()


def _row_dict(row) -> dict:
    return {
        "id": row[0],
        "user_id": row[1],
        "phone": row[2],
        "alert_phone": row[3],
        "deadline": row[4].isoformat(),
        "status": row[5],
    }

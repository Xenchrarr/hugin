from __future__ import annotations

import json
import os
import socket
import uuid
from dataclasses import dataclass, field
from typing import Callable

from src.persistence.JobDb import JobDb
from src.workflows.contracts import StepResult


@dataclass(frozen=True)
class IncidentActionResult:
    claimed: bool
    completed: bool
    attempt: int | None = None
    output: dict = field(default_factory=dict)
    outcome: str = "succeeded"
    summary: str = ""


class IncidentActionStore:
    """Lease and result ledger for idempotent response-workflow side effects."""

    def __init__(self, owner: str | None = None):
        self.db = JobDb.instance()
        self.owner = owner or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"

    def claim(self, incident_id: str, action_key: str, lease_seconds: int = 300) -> IncidentActionResult:
        self.db.execute("""INSERT INTO monitor_incident_actions(incident_id,action_key)
            VALUES(%s,%s) ON CONFLICT DO NOTHING""", (incident_id, action_key))
        row = self.db.execute("""UPDATE monitor_incident_actions SET status='Running',
            attempts=attempts+1,lease_owner=%s,lease_until=NOW()+make_interval(secs=>%s),updated_at=NOW()
            WHERE incident_id=%s AND action_key=%s AND status IN ('Pending','Error','Running')
            AND (lease_until IS NULL OR lease_until<NOW())
            RETURNING attempts""", (self.owner, lease_seconds, incident_id, action_key)).fetchone()
        self.db.commit()
        if row:
            return IncidentActionResult(True, False, row[0])
        existing = self.db.execute("""SELECT status,attempts,output,outcome,summary
            FROM monitor_incident_actions WHERE incident_id=%s AND action_key=%s""",
            (incident_id, action_key)).fetchone()
        return IncidentActionResult(False, existing[0] == 'Finished', existing[1],
                                    existing[2], existing[3], existing[4])

    def finish(self, incident_id: str, action_key: str, result: StepResult) -> None:
        self.db.execute("""UPDATE monitor_incident_actions SET status='Finished',output=%s,
            outcome=%s,summary=%s,lease_owner=NULL,lease_until=NULL,updated_at=NOW()
            WHERE incident_id=%s AND action_key=%s AND lease_owner=%s""",
            (json.dumps(result.output), result.outcome, result.summary,
             incident_id, action_key, self.owner))
        self.db.commit()

    def fail(self, incident_id: str, action_key: str, error: Exception) -> None:
        self.db.execute("""UPDATE monitor_incident_actions SET status='Error',error=%s,
            lease_owner=NULL,lease_until=NULL,updated_at=NOW()
            WHERE incident_id=%s AND action_key=%s AND lease_owner=%s""",
            (json.dumps({"type": type(error).__name__, "message": str(error)}),
             incident_id, action_key, self.owner))
        self.db.commit()

    def execute_once(self, incident_id: str, action_key: str,
                     handler: Callable[[], StepResult | dict | None]) -> StepResult:
        try:
            claim = self.claim(incident_id, action_key)
            if claim.completed:
                return StepResult(claim.outcome, claim.output, claim.summary)
            if not claim.claimed:
                raise RuntimeError(f"Incident action is already running: {action_key}")
            value = handler()
            result = value if isinstance(value, StepResult) else StepResult(output=value or {})
            if not isinstance(result.output, dict):
                raise ValueError("Incident action output must be an object")
            self.finish(incident_id, action_key, result)
            return result
        except Exception as exc:
            self.fail(incident_id, action_key, exc)
            raise
        finally:
            self.db.close_connection()

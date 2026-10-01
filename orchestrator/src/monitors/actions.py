from __future__ import annotations

from typing import Callable

from src.services.monitoring.incident_actions import IncidentActionStore
from src.workflows.contracts import StepContext, StepHandler, StepResult, WorkflowStepError


class IncidentActionExecution:
    """Persist and replay an incident side effect instead of performing it twice."""

    def __init__(self, store_factory: Callable[[], IncidentActionStore] = IncidentActionStore):
        self._store_factory = store_factory

    def execute(self, handler: StepHandler, context: StepContext, inputs: dict) -> StepResult:
        incident_id = inputs.get("incident_id")
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise WorkflowStepError("Incident action requires incident_id")
        context.check_cancellation()
        return self._store_factory().execute_once(
            incident_id,
            context.step_key,
            lambda: handler(context, inputs),
        )

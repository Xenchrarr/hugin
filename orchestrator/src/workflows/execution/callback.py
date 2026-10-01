from __future__ import annotations

from typing import Callable, Mapping

from src.services.core.callback_registry import CallbackRegistry, workflow_step_callback_id
from src.workflows.contracts import (
    StepContext,
    StepHandler,
    StepOutcome,
    StepResult,
    WorkflowStepError,
)

Timeout = float | Callable[[], float]


class CallbackExecution:
    """Run a step whose final result is delivered by an asynchronous callback."""

    def __init__(
        self,
        callbacks: CallbackRegistry,
        timeout: Timeout,
        label: str,
        status_outcomes: Mapping[str, StepOutcome] | None = None,
    ):
        self._callbacks = callbacks
        self._timeout = timeout
        self._label = label
        self._status_outcomes = dict(status_outcomes or {
            "Finished": "succeeded",
            "Partial": "partial",
            "PartialSuccess": "partial",
            "Nothing": "nothing",
        })

    def execute(self, handler: StepHandler, context: StepContext, inputs: dict) -> StepResult:
        context.check_cancellation()
        callback_id = workflow_step_callback_id(context.step_run_id)
        self._callbacks.register(callback_id)
        try:
            handler(context, inputs)
            status, output, summary = self._callbacks.wait(
                callback_id, timeout=self._timeout_seconds())
        finally:
            self._callbacks.cleanup(callback_id)

        outcome = self._status_outcomes.get(status)
        if outcome is None:
            raise WorkflowStepError(summary or f"{self._label} failed")
        return StepResult(
            outcome=outcome,
            output=output or {},
            summary=summary or f"{self._label} finished",
        )

    def _timeout_seconds(self) -> float:
        timeout = self._timeout() if callable(self._timeout) else self._timeout
        if (not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
                or timeout <= 0):
            raise ValueError("Callback step timeout must be a positive number")
        return float(timeout)

from __future__ import annotations

import math
import time

from ..contracts import StepContext, StepResult, WorkflowStepError
from ..step import step


@step(
    "core.echo",
    description="Return one JSON value unchanged",
    input_schema={
        "type": "object",
        "required": ["value"],
        "properties": {
            "value": {"description": "Any JSON value to return unchanged"},
        },
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "required": ["value"],
        "properties": {
            "value": {"description": "The unchanged input value"},
        },
        "additionalProperties": False,
    },
    idempotent=True,
)
def echo_step(_context: StepContext, inputs: dict) -> StepResult:
    return StepResult(output={"value": inputs["value"]}, summary="Value returned")


@step("core.wait", description="Pause while remaining cancellation-aware",
      input_schema={"type": "object", "required": ["seconds"],
                    "properties": {"seconds": {"type": "number", "minimum": 0,
                                                "description": "Number of seconds to wait"}},
                    "additionalProperties": False},
      output_schema={"type": "object", "required": ["waited_seconds"],
                     "properties": {"waited_seconds": {"type": "number",
                                                        "description": "Completed wait duration"}},
                     "additionalProperties": False}, idempotent=True)
def wait_step(context: StepContext, inputs: dict) -> StepResult:
    seconds = inputs.get("seconds")
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
        raise WorkflowStepError("Wait duration must be a finite, non-negative number")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        context.check_cancellation()
        time.sleep(min(0.25, deadline - time.monotonic()))
    return StepResult(output={"waited_seconds": seconds}, summary=f"Waited {seconds} seconds")

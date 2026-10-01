from __future__ import annotations

import math
import time

from ..contracts import StepContext, StepResult, WorkflowStepError
from ..step import step


@step("core.echo", description="Return input as structured output",
      input_schema={"type": "object"}, output_schema={"type": "object"}, idempotent=True)
def echo_step(_context: StepContext, inputs: dict) -> StepResult:
    return StepResult(output=inputs, summary="Input returned")


@step("core.wait", description="Pause while remaining cancellation-aware",
      input_schema={"type": "object", "required": ["seconds"],
                    "properties": {"seconds": {"type": "number", "minimum": 0}}},
      output_schema={"type": "object"}, idempotent=True)
def wait_step(context: StepContext, inputs: dict) -> StepResult:
    seconds = inputs.get("seconds")
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
        raise WorkflowStepError("Wait duration must be a finite, non-negative number")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        context.check_cancellation()
        time.sleep(min(0.25, deadline - time.monotonic()))
    return StepResult(summary=f"Waited {seconds} seconds")

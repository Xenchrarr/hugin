from __future__ import annotations

from src.workflows import StepContext, StepResult, WorkflowStepError, step


@step(
    "powershell.run_script",
    description="Run an approved PowerShell script and retain its structured result",
    input_schema={
        "type": "object",
        "required": ["script_name"],
        "properties": {
            "script_name": {"type": "string", "minLength": 1,
                            "description": "Approved script name"},
            "parameters": {"type": "object", "default": {},
                           "description": "Named parameters passed to the script"},
        },
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "required": ["status", "result"],
        "properties": {
            "status": {"type": "string", "description": "PowerShell runner status"},
            "result": {"description": "Structured or scalar result returned by the script"},
        },
        "additionalProperties": False,
    },
)
def powershell_run_script_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.powershell_service import run_script

    context.check_cancellation()
    response = run_script(inputs["script_name"], inputs.get("parameters", {}))
    if not isinstance(response, dict):
        return StepResult(output={"status": "Finished", "result": response})
    status = response.get("status", "Finished")
    outcome = {
        "Finished": "succeeded",
        "Partial": "partial",
        "PartialSuccess": "partial",
        "Nothing": "nothing",
    }.get(status)
    if outcome is None:
        raise WorkflowStepError(response.get("message") or "PowerShell script failed")
    result = response.get("result", response)
    return StepResult(
        outcome=outcome,
        output={"status": status, "result": result},
        summary=response.get("message") or f"Script {inputs['script_name']} finished",
    )

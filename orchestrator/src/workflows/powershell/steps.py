from __future__ import annotations

from src.workflows import StepContext, StepResult, WorkflowStepError, step


@step(
    "powershell.run_script",
    description="Run an approved PowerShell script and retain its structured result",
    input_schema={
        "type": "object",
        "required": ["script_name"],
        "properties": {
            "script_name": {"type": "string", "minLength": 1},
            "parameters": {"type": "object", "default": {}},
        },
        "additionalProperties": False,
    },
    output_schema={"type": "object"},
)
def powershell_run_script_step(context: StepContext, inputs: dict) -> StepResult:
    from src.services.external.powershell_service import run_script

    context.check_cancellation()
    response = run_script(inputs["script_name"], inputs.get("parameters", {}))
    if not isinstance(response, dict):
        return StepResult(output={"result": response})
    status = response.get("status", "Finished")
    outcome = {
        "Finished": "succeeded",
        "Partial": "partial",
        "PartialSuccess": "partial",
        "Nothing": "nothing",
    }.get(status)
    if outcome is None:
        raise WorkflowStepError(response.get("message") or "PowerShell script failed")
    output = response.get("result", response)
    if not isinstance(output, dict):
        output = {"result": output}
    return StepResult(
        outcome=outcome,
        output=output,
        summary=response.get("message") or f"Script {inputs['script_name']} finished",
    )

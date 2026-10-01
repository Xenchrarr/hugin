from src.workflows import workflow

from .steps import powershell_run_script_step


workflow(
    "run_script",
    powershell_run_script_step,
    version=1,
    description="Run a PowerShell script with structured parameters and callback result",
    input_schema=powershell_run_script_step.spec.input_schema,
)

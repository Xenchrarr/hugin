from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.api.powershell_runner import POWERSHELL_SCRIPT_TIMEOUT
from src.api.powershell_runner.script_runner import test_script, run_generic_script
from src.services.core.callback_registry import (
    callback_registry, job_run_callback_id, workflow_step_callback_id,
)

_SUCCESS = {'Finished', 'Partial', 'PartialSuccess', 'Nothing'}


def _run(start):
    local = ThreadLocalSingleton.instance().thread_local
    run_id = str(getattr(local, 'job_run_id', '') or '')
    step_id = getattr(local, 'step_run_id', None)
    if not run_id:
        raise RuntimeError('PowerShell scripts require a job_run_id')
    key = workflow_step_callback_id(str(step_id)) if step_id else job_run_callback_id(run_id)
    callback_registry.register(key)
    try:
        start(run_id, str(step_id) if step_id else None)
        status, result, message = callback_registry.wait(key, POWERSHELL_SCRIPT_TIMEOUT)
    finally:
        callback_registry.cleanup(key)
    if status not in _SUCCESS:
        raise RuntimeError(message or result.get('error') or 'PowerShell script failed')
    return {'status': status, 'result': result, 'message': message}


def run_test_script():
    return _run(lambda run_id, step_id: test_script(run_id, step_id))


def run_script(script_name: str, user_params: dict):
    return _run(lambda run_id, step_id: run_generic_script(
        script_name=script_name, params=user_params,
        job_run_id=run_id, step_run_id=step_id,
    ))

import os

from src.api.orchestrator import ORCHESTRATOR_API_URL, session


def post_result(job_run_id, status, result, message='', step_run_id=None):
    body = {'job_run_id': str(job_run_id), 'status': status,
            'result': result, 'message': message}
    if step_run_id:
        body['step_run_id'] = str(step_run_id)
    response = session.post(
        f'{ORCHESTRATOR_API_URL}/api/powershell/result', json=body, timeout=30,
        headers={'X-Service-Key': os.environ.get('SERVICE_KEY', '')})
    if response.status_code != 200:
        raise RuntimeError(
            f'Orchestrator callback failed: {response.status_code}: {response.text[:200]}')

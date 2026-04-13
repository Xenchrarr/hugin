import json
from datetime import datetime

from flask import Blueprint, request

from src.api.powershell_runner.script_runner import list_scripts
from src.models.orchestrator.Job import Job
from src.services.job_service import get_jobs, create_job, run_job_once
from src.persistence.ScriptReasonStorage import ScriptReasonStorage

_reason_storage = ScriptReasonStorage()

scripts_blueprint = Blueprint('scripts', __name__)


_placeholder_job_id = None


def _get_or_create_placeholder_job() -> Job:
    """Return the persistent run_script job, creating it on first call."""
    global _placeholder_job_id

    if _placeholder_job_id is not None:
        from src.services.job_service import get_job
        job = get_job(_placeholder_job_id)
        if job is not None:
            return job

    for job in get_jobs():
        if job.job_type == 'run_script':
            _placeholder_job_id = job.id
            return job

    now = datetime.now()
    new_job = Job(
        id=0,
        name='Run Script',
        enabled=False,
        job_type='run_script',
        hour=0,
        minute=0,
        created_at=now,
        updated_at=now,
        trigger='once',
        param='',
        description='Placeholder job for ad-hoc script execution',
        grouping_value='scripts',
    )
    created = create_job(new_job)
    _placeholder_job_id = created.id
    return created


@scripts_blueprint.route('/list', methods=['GET'])
def get_scripts():
    """List available PowerShell scripts and their parameters."""
    try:
        return {'scripts': [], 'status': 200}, 200

        # result = list_scripts(SCRIPTS_FOLDER)
        # scripts = result.get('scripts', [])
        #
        # # Attach per-script reason options
        # reason_options = _reason_storage.get_all_grouped()
        # for s in scripts:
        #     s['reason_options'] = reason_options.get(s.get('name', ''), [])
        #
        # return {'scripts': scripts, 'status': 200}, 200
    except Exception as e:
        return {'message': str(e), 'status': 500}, 500


@scripts_blueprint.route('/run', methods=['POST'])
def run_script():
    """Run a PowerShell script via the job engine."""
    try:
        data = request.get_json(force=True)
        script_name = data.get('script_name')
        params = data.get('params', {})

        if not script_name:
            return {'message': 'script_name is required', 'status': 400}, 400

        run_by = data.get('run_by', 'user')
        run_by_group = 'user'

        placeholder = _get_or_create_placeholder_job()

        run_params = dict(params)
        run_params['script_name'] = script_name

        reason = data.get('reason')
        if not reason or (not reason.get('selected') and not reason.get('freeText')):
            return {'message': 'A reason for running this script is required', 'status': 400}, 400

        metadata = {
            'script_name': script_name,
            'ControlRoom': params.get('ControlRoom'),
            'reason': {
                'selected': reason.get('selected') or None,
                'freeText': reason.get('freeText') or None,
            },
        }

        job = Job(
            id=placeholder.id,
            name=script_name,
            enabled=placeholder.enabled,
            job_type='run_script',
            hour=0,
            minute=0,
            created_at=placeholder.created_at,
            updated_at=placeholder.updated_at,
            trigger='once',
            param=json.dumps(run_params),
            description=placeholder.description,
            grouping_value=placeholder.grouping_value,
        )

        job_run_id = run_job_once(job, run_by=run_by, run_by_group=run_by_group, metadata=metadata)

        return {
            'message': 'Script job started',
            'status': 200,
            'job_run_id': str(job_run_id),
        }
    except Exception as e:
        return {
            'message': f'Error: {e}',
            'status': 500,
            'error': str(e),
        }, 500

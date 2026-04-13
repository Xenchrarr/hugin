from flask import Blueprint, request

from src.jobs_registry import jobs_registry
from src.models.orchestrator.Job import Job
from src.services.job_service import (
    get_jobs,
    get_enabled_jobs,
    update_job,
    delete_job as delete_job_service,
    run_job_once,
    get_grouping_values,
    get_running_jobs_from_scheduler,
    get_status_values,
    get_job,
    create_job,
)

jobs_blueprint = Blueprint('jobs', __name__)


@jobs_blueprint.route('/list', methods=['GET'])
def jobs():
    try:
        available_jobs = get_jobs()
        return [job.to_dict() for job in available_jobs]
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/enabled_list', methods=['GET'])
def enabled_jobs():
    try:
        available_jobs = get_enabled_jobs()
        return [job.to_dict() for job in available_jobs]
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/get_one', methods=['GET'])
def get_job_from_id():
    try:
        raw_job_id = request.args.get('job_id')
        if not raw_job_id:
            return {
                'message': 'Missing required query parameter: job_id',
                'status': 400,
            }, 400

        job_id = int(raw_job_id)
        job = get_job(job_id=job_id)

        if job is None:
            return {
                'message': 'Job not found',
                'status': 404,
            }, 404

        return job.to_dict()
    except ValueError as e:
        return {
            'message': 'Invalid job_id',
            'status': 400,
            'error': str(e),
        }, 400
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/types', methods=['GET'])
def available_types():
    return [
        {
            "job_type": key,
            "function_name": value['function'].__name__,
            "description": value['description'],
        }
        for key, value in jobs_registry.items()
    ]


@jobs_blueprint.route('/', methods=['POST'])
def upsert_job():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {
                'message': 'Missing or invalid JSON body',
                'status': 400,
            }, 400

        job = Job.from_dict(data)

        if job.id is None or job.id == 0:
            create_job(job)
            return job.to_dict()

        updated_job = update_job(job)
        return updated_job.to_dict() if updated_job is not None else job.to_dict()

    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/start', methods=['POST'])
def run_job_now():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {
                'message': 'Missing or invalid JSON body',
                'status': 400,
            }, 400

        job = Job.from_dict(data)
        run_by = data.get('run_by', 'user')
        job_run_id = run_job_once(job, run_by=run_by, run_by_group='user')

        return {
            'message': 'Job started',
            'status': 200,
            'job_run_id': str(job_run_id),
        }
    except Exception as e:
        return {
            'message': f"Error: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/<job_id>', methods=['DELETE'])
def delete_job_route(job_id):
    try:
        # data = request.get_json(silent=True)
        # if not data:
        #     return {
        #         'message': 'Missing or invalid JSON body',
        #         'status': 400,
        #     }, 400

        # job_id = data.get('id')
        if job_id is None:
            return {
                'message': 'Missing required field: id',
                'status': 400,
            }, 400

        delete_job_service(job_id)

        return {
            'message': 'Job deleted',
            'status': 200,
        }
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/grouping', methods=['GET'])
def get_groupings():
    try:
        return get_grouping_values()
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/status', methods=['GET'])
def get_statuses():
    try:
        return get_status_values()
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@jobs_blueprint.route('/running', methods=['GET'])
def get_running_jobs():
    try:
        queued_jobs = get_running_jobs_from_scheduler()
        return [job.to_dict() for job in queued_jobs]
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500
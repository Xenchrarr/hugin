from flask import Blueprint, request

from src.services.core.job_log_service import (
    get_logs_for_job_run,
    get_request_log_for_job_run,
    get_total_count_request_log_for_job_run,
)

job_log_blueprint = Blueprint('job_log', __name__)


@job_log_blueprint.route('/getforjob', methods=['GET'])
def get_job_logs():
    try:
        job_run_id = request.args.get('job_run_id')
        if not job_run_id:
            return {
                'message': 'Missing required query parameter: job_run_id',
                'status': 400,
            }, 400

        logs = get_logs_for_job_run(job_run_id)
        return [log.to_dict() for log in logs]

    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'error': str(e),
        }, 500


@job_log_blueprint.route('/requests', methods=['GET'])
def get_job_requests():
    try:
        job_run_id = request.args.get('job_run_id')
        if not job_run_id:
            return {
                'message': 'Missing required query parameter: job_run_id',
                'status': 400,
            }, 400

        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))

        logs = get_request_log_for_job_run(job_run_id, page, page_size)
        return [log.to_dict() for log in logs]

    except ValueError as e:
        return {
            'message': 'Invalid page or page_size',
            'status': 400,
            'error': str(e),
        }, 400
    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'error': str(e),
        }, 500


@job_log_blueprint.route('/requests_total_count', methods=['GET'])
def count_total_runs():
    try:
        job_run_id = request.args.get('job_run_id')
        if not job_run_id:
            return {
                'message': 'Missing required query parameter: job_run_id',
                'status': 400,
            }, 400

        total = get_total_count_request_log_for_job_run(job_run_id)
        return {
            'total': total
        }

    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'error': str(e),
        }, 500
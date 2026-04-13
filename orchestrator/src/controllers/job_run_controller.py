

from flask import Blueprint, request

from src.services.core.job_run_service import get_job_runs, get_total_job_runs, get_job_run_by_id
from src.services.core.job_service import cancel_job_run
from src.services.core.utils import comma_separated_params_to_list

job_run_blueprint = Blueprint('job_run', __name__)


def _normalize_list_param(param_name: str) -> list[str]:
    values = request.args.getlist(param_name)

    if len(values) == 1 and ',' in values[0]:
        values = comma_separated_params_to_list(values[0])

    return values


@job_run_blueprint.route('/list', methods=['GET'])
def list_runs():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))

        grouping_values = _normalize_list_param('grouping')
        status_values = _normalize_list_param('status')

        runs = get_job_runs(page, page_size, grouping_values, status_values)
        return [run.to_dict() for run in runs]

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


@job_run_blueprint.route('/total_count', methods=['GET'])
def count_total_runs():
    try:
        grouping_values = _normalize_list_param('grouping')
        status_values = _normalize_list_param('status')

        total = get_total_job_runs(grouping_values, status_values)
        return {
            'total': total
        }

    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'error': str(e),
        }, 500


@job_run_blueprint.route('/cancel', methods=['POST'])
def cancel_run():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {
                'message': 'Missing or invalid JSON body',
                'status': 400,
            }, 400

        job_run_id = data.get('job_run_id')
        if not job_run_id:
            return {
                'message': 'Missing required field: job_run_id',
                'status': 400,
            }, 400

        cancel_job_run(job_run_id)

        return {
            'message': 'Cancellation requested',
            'status': 200,
        }
    except ValueError as e:
        return {
            'message': str(e),
            'status': 400,
            'error': str(e),
        }, 400
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@job_run_blueprint.route('/get', methods=['GET'])
def get_single_run():
    try:
        job_run_id = request.args.get('job_run_id')
        if not job_run_id:
            return {
                'message': 'Missing required query parameter: job_run_id',
                'status': 400,
            }, 400

        run = get_job_run_by_id(job_run_id)
        if run is None:
            return {
                'message': 'Job run not found',
                'status': 404,
            }, 404

        return run.to_dict()

    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'error': str(e),
        }, 500



@job_run_blueprint.route('/delete', methods=['DELETE'])
def delete_run():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {
                'message': 'Missing or invalid JSON body',
                'status': 400,
            }, 400

        job_run_id = data.get('job_run_id')
        if not job_run_id:
            return {
                'message': 'Missing required field: job_run_id',
                'status': 400,
            }, 400

        from src.services.core.job_run_service import delete_job_run
        delete_job_run(job_run_id)

        return {
            'message': 'Job run and logs deleted',
            'status': 200,
        }
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500
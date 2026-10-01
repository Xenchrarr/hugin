from flask import Blueprint, request
from src.auth import require_service_key

from src.models.api.LogFromLogController import LogFromLogController
from src.persistence.DatabaseLogger import DatabaseLogger

logger_blueprint = Blueprint("logger", __name__)


@logger_blueprint.route('/log', methods=['POST'])
@require_service_key
def log_message():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {
                'message': 'Missing or invalid JSON body',
                'status': 400,
            }, 400

        job_log = LogFromLogController.from_dict(data)
        db_logger = DatabaseLogger()
        db_logger.log_from_api(job_log)

        return {
            'message': job_log.log_text,
            'status': 200,
        }, 200

    except Exception as e:

        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@logger_blueprint.route('/log/batch', methods=['POST'])
@require_service_key
def log_batch():
    data = request.get_json(silent=True)
    if not isinstance(data, list) or len(data) > 500:
        return {'message': 'Expected a list of at most 500 logs', 'status': 400}, 400
    try:
        parsed = [LogFromLogController.from_dict(item) for item in data]
        rows = [
            (item.job_run_id, item.step_run_id, item.severity,
             DatabaseLogger._truncate_or_upload(item.log_text, 2000, item.job_run_id, f'{item.severity}_message'),
             DatabaseLogger._truncate_or_upload(item.stack_trace, 2000, item.job_run_id, f'{item.severity}_stack_trace'))
            for item in parsed
        ]
        DatabaseLogger().log_batch(rows)
        return {'accepted': len(rows), 'status': 200}, 200
    except Exception as exc:
        return {'message': str(exc), 'status': 500}, 500

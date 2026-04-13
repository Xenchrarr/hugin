from flask import Blueprint, request

from src.models.api.LogFromLogController import LogFromLogController
from src.persistence.DatabaseLogger import DatabaseLogger

logger_blueprint = Blueprint("logger", __name__)


@logger_blueprint.route('/log', methods=['POST'])
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
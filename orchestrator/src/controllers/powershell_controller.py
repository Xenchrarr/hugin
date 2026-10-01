from flask import Blueprint, jsonify, request
from src.auth import require_service_key

from src.services.core.callback_registry import (
    callback_registry, job_run_callback_id, workflow_step_callback_id,
)

powershell_blueprint = Blueprint('powershell_callback', __name__)


@powershell_blueprint.route('/result', methods=['POST'])
@require_service_key
def result():
    body = request.get_json(silent=True) or {}
    run_id, step_id = body.get('job_run_id'), body.get('step_run_id')
    if not run_id:
        return jsonify({'message': 'job_run_id is required'}), 400
    key = workflow_step_callback_id(str(step_id)) if step_id else job_run_callback_id(str(run_id))
    found = callback_registry.signal(
        key, body.get('status', 'Error'), body.get('result') or {}, body.get('message', ''))
    return ((jsonify({'message': 'ok'}), 200) if found
            else (jsonify({'message': 'No pending callback'}), 404))

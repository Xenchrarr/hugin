import traceback

from flask import Blueprint, jsonify, request

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.services import homeassistant_service
from src.services.log_service import log_info, log_error

home_blueprint = Blueprint("home", __name__)


@home_blueprint.route("/trigger", methods=["POST"])
def trigger_automation():
    job_run_id = None
    try:
        body = request.get_json(force=True)
        entity_id = body.get("entity_id")
        if not entity_id:
            return jsonify({"error": "entity_id is required"}), 400

        job_run_id = body.get("job_run_id")
        if job_run_id:
            thread_local = ThreadLocalSingleton.instance().thread_local
            thread_local.job_run_id = job_run_id
            log_info(f"Triggering automation: {entity_id} with job_run_id: {job_run_id}")

        variables = body.get("variables")
        result = homeassistant_service.trigger_automation(entity_id, variables=variables)

        if job_run_id:
            log_info(f"Automation {entity_id} triggered successfully")

        return jsonify({"ok": True, "result": result})
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        if job_run_id:
            log_error(f"Automation trigger failed: {e}", stack_trace=stack_trace)
        return jsonify({"ok": False, "error": str(e)}), 500

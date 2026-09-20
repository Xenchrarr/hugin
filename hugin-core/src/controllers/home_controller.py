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


@home_blueprint.route("/states")
def get_states():
    """Return a compact subset of Home Assistant states for SMS status views."""
    raw_entities = request.args.get("entities", "")
    entity_ids = [item.strip() for item in raw_entities.split(",") if item.strip()]
    if not entity_ids:
        return jsonify({"states": []})
    if len(entity_ids) > 20:
        return jsonify({"error": "at most 20 entities are allowed"}), 400

    try:
        all_states = homeassistant_service.get_api().get("/api/states") or []
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    by_id = {item.get("entity_id"): item for item in all_states}
    states = []
    for entity_id in entity_ids:
        data = by_id.get(entity_id) or {}
        attrs = data.get("attributes") or {}
        states.append({
            "entity_id": entity_id,
            "state": data.get("state", "unavailable"),
            "friendly_name": attrs.get("friendly_name", entity_id),
            "unit": attrs.get("unit_of_measurement", ""),
        })
    return jsonify({"states": states})

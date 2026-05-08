import traceback

from flask import Blueprint, jsonify, request

from src.services import simplenote_service
from src.services.log_service import log_error, log_info

ideas_blueprint = Blueprint("ideas", __name__)


@ideas_blueprint.route("/list")
def get_list():
    try:
        content = simplenote_service.get_ideas()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@ideas_blueprint.route("/add", methods=["POST"])
def add_item():
    job_run_id = None
    try:
        body = request.get_json(force=True)
        item = body.get("item")
        if not item:
            return jsonify({"error": "item is required"}), 400

        job_run_id = body.get("job_run_id")
        if job_run_id:
            from src.ThreadLocalSingleton import ThreadLocalSingleton
            thread_local = ThreadLocalSingleton.instance().thread_local
            thread_local.job_run_id = job_run_id
            log_info(f"Adding item to ideas: {item}")

        simplenote_service.add_to_ideas(item)

        if job_run_id:
            log_info(f"Item '{item}' added to ideas")

        return jsonify({"ok": True, "added": item})
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        if job_run_id:
            log_error(f"Failed to add item to ideas: {e}", stack_trace=stack_trace)
        return jsonify({"ok": False, "error": str(e)}), 500

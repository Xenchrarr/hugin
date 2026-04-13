import traceback

from flask import Blueprint, jsonify, request

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.services import simplenote_service
from src.services.log_service import log_info, log_error

shopping_blueprint = Blueprint("shopping", __name__)


@shopping_blueprint.route("/list")
def get_list():
    try:
        content = simplenote_service.get_shopping_list()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@shopping_blueprint.route("/add", methods=["POST"])
def add_item():
    job_run_id = None
    try:
        body = request.get_json(force=True)
        item = body.get("item")
        if not item:
            return jsonify({"error": "item is required"}), 400

        job_run_id = body.get("job_run_id")
        if job_run_id:
            thread_local = ThreadLocalSingleton.instance().thread_local
            thread_local.job_run_id = job_run_id
            log_info(f"Adding item to shopping list: {item}")

        simplenote_service.add_to_shopping_list(item)

        if job_run_id:
            log_info(f"Item '{item}' added to shopping list")

        return jsonify({"ok": True, "added": item})
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        if job_run_id:
            log_error(f"Failed to add item to shopping list: {e}", stack_trace=stack_trace)
        return jsonify({"ok": False, "error": str(e)}), 500


@shopping_blueprint.route("/remove", methods=["DELETE"])
def remove_item():
    job_run_id = None
    try:
        body = request.get_json(force=True)
        item = body.get("item")
        if not item:
            return jsonify({"error": "item is required"}), 400

        job_run_id = body.get("job_run_id")
        if job_run_id:
            thread_local = ThreadLocalSingleton.instance().thread_local
            thread_local.job_run_id = job_run_id
            log_info(f"Removing item from shopping list: {item}")

        removed = simplenote_service.remove_from_shopping_list(item)
        if not removed:
            if job_run_id:
                log_info(f"Item '{item}' not found in shopping list")
            return jsonify({"ok": False, "error": "Item not found"}), 404

        if job_run_id:
            log_info(f"Item '{item}' removed from shopping list")

        return jsonify({"ok": True, "removed": item})
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        if job_run_id:
            log_error(f"Failed to remove item from shopping list: {e}", stack_trace=stack_trace)
        return jsonify({"ok": False, "error": str(e)}), 500

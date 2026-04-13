from flask import Blueprint, jsonify, request

from src.services.core.script_permission_service import (
    get_all_script_permissions,
    get_allowed_script_names,
    upsert_script_permission,
    delete_script_permission,
)

script_permission_blueprint = Blueprint("script_permissions", __name__)


@script_permission_blueprint.route("/list", methods=["GET"])
def list_permissions():
    try:
        permissions = get_all_script_permissions()
        return [p.to_dict() for p in permissions]
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500


@script_permission_blueprint.route("/allowed", methods=["GET"])
def list_allowed():
    try:
        names = get_allowed_script_names()
        return jsonify(names)
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500


@script_permission_blueprint.route("/", methods=["PUT"])
def upsert_permission():
    try:
        data = request.get_json(silent=True)
        if not data or "script_name" not in data:
            return {"message": "script_name is required", "status": 400}, 400

        script_name = data["script_name"]
        allowed = bool(data.get("allowed_for_servicedesk", False))
        upsert_script_permission(script_name, allowed)
        return {"message": "ok"}
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500


@script_permission_blueprint.route("/<path:script_name>", methods=["DELETE"])
def remove_permission(script_name: str):
    try:
        delete_script_permission(script_name)
        return {"message": "ok"}
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500

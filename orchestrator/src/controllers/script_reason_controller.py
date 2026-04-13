from flask import Blueprint, jsonify, request

from src.persistence.ScriptReasonStorage import ScriptReasonStorage

script_reason_blueprint = Blueprint("script_reasons", __name__)

_storage = ScriptReasonStorage()


@script_reason_blueprint.route("/list", methods=["GET"])
def list_options():
    try:
        options = _storage.get_all()
        return [o.to_dict() for o in options]
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500


@script_reason_blueprint.route("/", methods=["POST"])
def create_option():
    try:
        data = request.get_json(silent=True)
        if not data or not data.get("script_name") or not data.get("option_label"):
            return {"message": "script_name and option_label are required", "status": 400}, 400

        _storage.insert(
            script_name=data["script_name"],
            option_label=data["option_label"],
            display_order=int(data.get("display_order", 0)),
        )
        return {"message": "ok"}
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500


@script_reason_blueprint.route("/", methods=["PUT"])
def update_option():
    try:
        data = request.get_json(silent=True)
        if not data or not data.get("id") or not data.get("option_label"):
            return {"message": "id and option_label are required", "status": 400}, 400

        _storage.update(
            option_id=int(data["id"]),
            option_label=data["option_label"],
            display_order=int(data.get("display_order", 0)),
        )
        return {"message": "ok"}
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500


@script_reason_blueprint.route("/<int:option_id>", methods=["DELETE"])
def delete_option(option_id: int):
    try:
        _storage.delete(option_id)
        return {"message": "ok"}
    except Exception as e:
        return {"message": f"Something went wrong: {e}", "status": 500}, 500

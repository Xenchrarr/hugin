from flask import Blueprint, request

from src.auth import require_service_key
from src.services.core.checkin_service import acknowledge_checkin, create_checkin

checkin_blueprint = Blueprint("checkins", __name__)


@checkin_blueprint.route("/", methods=["POST"])
@require_service_key
def create():
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
        minutes = max(1, min(int(data.get("minutes")), 1440))
        phone = str(data.get("phone") or "").strip()
        if not phone:
            raise ValueError("phone is required")
        return create_checkin(user_id, phone, minutes), 201
    except (TypeError, ValueError) as exc:
        return {"message": str(exc)}, 400


@checkin_blueprint.route("/ack", methods=["POST"])
@require_service_key
def acknowledge():
    data = request.get_json(silent=True) or {}
    try:
        result = acknowledge_checkin(int(data.get("user_id")))
    except (TypeError, ValueError) as exc:
        return {"message": str(exc)}, 400
    return (result, 200) if result else ({"message": "No active check-in"}, 404)

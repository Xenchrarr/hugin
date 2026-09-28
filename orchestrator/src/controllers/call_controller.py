from __future__ import annotations

import requests
from flask import Blueprint, g

from src.auth import require_auth, require_service_key
from src.persistence.UserStorage import UserStorage
from src.services.external.call_service import ring_phone


call_blueprint = Blueprint("calls", __name__)


@call_blueprint.route("/me", methods=["POST"])
@require_auth
def call_me():
    user = UserStorage().get_user(int(g.jwt_payload["sub"]))
    if user is None:
        return {"message": "User not found"}, 404

    phone = str(user.phone_number or "").strip()
    if not phone:
        return {"message": "Add a phone number to your Hugin user first"}, 400

    try:
        return ring_phone(phone, ring_seconds=20), 200
    except requests.HTTPError as exc:
        response = exc.response
        message = "The modem rejected the call"
        if response is not None:
            try:
                message = response.json().get("error", message)
            except ValueError:
                pass
        return {"message": message}, response.status_code if response is not None else 502
    except requests.RequestException:
        return {"message": "The modem service is unavailable"}, 502
    except RuntimeError as exc:
        return {"message": str(exc)}, 503


@call_blueprint.route("/user/<int:user_id>", methods=["POST"])
@require_service_key
def call_user(user_id: int):
    user = UserStorage().get_user(user_id)
    if user is None or not user.phone_number:
        return {"message": "User or phone number not found"}, 404
    try:
        return ring_phone(str(user.phone_number), ring_seconds=20), 200
    except requests.RequestException:
        return {"message": "The modem service is unavailable"}, 502

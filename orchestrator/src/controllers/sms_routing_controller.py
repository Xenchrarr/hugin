from __future__ import annotations

from flask import Blueprint, request

from src.auth import require_service_key
from src.persistence.UserStorage import UserStorage
from src.services.core.sms_routing_service import SmsRoutingService


sms_routing_blueprint = Blueprint("sms_routing", __name__)
_service = SmsRoutingService()
_users = UserStorage()


def _owner_id(data: dict) -> int:
    raw = data.get("owner_user_id")
    if raw is not None:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError("owner_user_id must be an integer")
        if _users.get_user(value) is None:
            raise LookupError("owner user not found")
        return value
    phone = str(data.get("owner_phone") or "").strip()
    if not phone:
        raise ValueError("owner_user_id or owner_phone is required")
    user = _users.lookup_user_by_channel("sms", phone)
    if user is None:
        raise LookupError("owner user not found")
    return int(user.id)


def _error(exc: Exception):
    if isinstance(exc, LookupError):
        return {"message": str(exc)}, 404
    if isinstance(exc, ValueError):
        return {"message": str(exc)}, 400
    text = str(exc)
    if "unique" in text.lower() or "duplicate" in text.lower():
        return {"message": "alias is already assigned to another conversation"}, 409
    return {"message": "conversation routing failed"}, 500


@sms_routing_blueprint.route("/external-messages", methods=["POST"])
@require_service_key
def register_external_message():
    data = request.get_json(silent=True) or {}
    try:
        result = _service.register_external_message(
            owner_user_id=_owner_id(data),
            service=data.get("service"),
            integration_account=data.get("integration_account"),
            external_chat_id=data.get("external_chat_id"),
            alias=data.get("alias"),
            display_name=data.get("display_name"),
            event_id=data.get("event_id"),
            external_message_id=data.get("external_message_id"),
            body=data.get("body"),
            author=data.get("author"),
        )
        return result, 200 if result["duplicate"] else 201
    except Exception as exc:
        return _error(exc)


@sms_routing_blueprint.route("/outbound", methods=["POST"])
@require_service_key
def prepare_outbound():
    data = request.get_json(silent=True) or {}
    try:
        result = _service.prepare_outbound(
            owner_user_id=_owner_id(data),
            selector_type=str(data.get("selector_type") or ""),
            selector=data.get("selector"),
            body=data.get("body"),
            event_id=str(data.get("event_id") or "").strip() or None,
        )
        return result, 200 if result["duplicate"] else 201
    except Exception as exc:
        return _error(exc)


@sms_routing_blueprint.route("/outbound/<int:reference>/status", methods=["POST"])
@require_service_key
def update_outbound_status(reference: int):
    data = request.get_json(silent=True) or {}
    try:
        return _service.update_status(
            owner_user_id=_owner_id(data), reference=reference,
            status=str(data.get("status") or ""),
            detail=str(data.get("detail") or "").strip() or None,
            external_message_id=(str(data["external_message_id"])
                                 if data.get("external_message_id") is not None else None),
        )
    except Exception as exc:
        return _error(exc)


@sms_routing_blueprint.route("/chats", methods=["GET"])
@require_service_key
def list_chats():
    try:
        owner_user_id = _owner_id(request.args.to_dict())
        return _service.list_chats(
            owner_user_id, request.args.get("limit", 10), request.args.get("offset", 0)
        )
    except Exception as exc:
        return _error(exc)


@sms_routing_blueprint.route("/history", methods=["GET"])
@require_service_key
def history():
    try:
        owner_user_id = _owner_id(request.args.to_dict())
        before = request.args.get("before_reference")
        return _service.history(
            owner_user_id, str(request.args.get("alias") or ""),
            request.args.get("limit", 5), int(before) if before else None,
        )
    except Exception as exc:
        return _error(exc)


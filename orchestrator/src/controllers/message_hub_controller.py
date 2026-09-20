from __future__ import annotations

import base64
import binascii
import re

from flask import Blueprint, request

from src.auth import require_admin, require_auth_or_service_key, require_service_key
from src.services.core.message_hub_service import MessageHubService


message_hub_blueprint = Blueprint("message_hub", __name__)

_DELIVERY_STATUSES = {
    "pending",
    "leased",
    "retry_wait",
    "accepted",
    "held",
    "acknowledged",
    "expired",
    "dead",
    "uncertain",
    "cancelled",
}
_GATEWAY_KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
_GATEWAY_TYPES = {"sms", "telegram", "webhook"}


@message_hub_blueprint.route("/messages", methods=["POST"])
@require_service_key
def submit_message():
    data = request.get_json(silent=True) or {}
    payload = data.get("payload")
    deliveries = data.get("deliveries")
    if not isinstance(payload, dict) or not isinstance(deliveries, list):
        return {"message": "payload must be an object and deliveries must be a list"}, 400

    try:
        attachments = []
        raw_attachments = data.get("attachments", [])
        if raw_attachments is None:
            raw_attachments = []
        if not isinstance(raw_attachments, list):
            raise ValueError("attachments must be a list")
        for item in raw_attachments:
            if not isinstance(item, dict):
                raise ValueError("each attachment must be an object")
            encoded = item.get("data_base64")
            if not isinstance(encoded, str) or not encoded:
                raise ValueError("each attachment requires data_base64")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("attachment data_base64 is invalid") from None
            attachments.append({
                "content": content,
                "content_type": item.get("content_type"),
                "filename": item.get("filename"),
            })
        source_endpoint_id = data.get("source_endpoint_id")
        if source_endpoint_id is not None:
            source_endpoint_id = int(source_endpoint_id)
        message, queued = MessageHubService.instance().submit(
            direction=str(data.get("direction") or "outbound").strip().lower(),
            kind=str(data.get("kind") or "text").strip().lower(),
            payload=payload,
            deliveries=deliveries,
            attachments=attachments,
            metadata=data.get("metadata") or {},
            priority=int(data.get("priority", 50)),
            ttl_seconds=int(data.get("ttl_seconds", 30 * 24 * 60 * 60)),
            source_gateway_key=str(data.get("source_gateway_key") or "").strip() or None,
            source_endpoint_id=source_endpoint_id,
            external_id=str(data.get("external_id") or "").strip() or None,
            conversation_key=str(data.get("conversation_key") or "").strip() or None,
            idempotency_key=str(data.get("idempotency_key") or "").strip() or None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return {"message": str(exc)}, 400

    return {
        "message_id": message.id,
        "deliveries": [
            {"id": delivery.id, "status": delivery.status, "gateway_id": delivery.gateway_id}
            for delivery in queued
        ],
    }, 202


@message_hub_blueprint.route("/messages/<int:message_id>", methods=["GET"])
@require_auth_or_service_key
def get_message(message_id: int):
    service = MessageHubService.instance()
    message = service.get_message(message_id)
    if message is None:
        return {"message": "Message not found"}, 404
    result = message.to_dict()
    result["attachments"] = service.get_attachment_metadata(message_id)
    return result


@message_hub_blueprint.route("/deliveries", methods=["GET"])
@require_auth_or_service_key
def list_deliveries():
    status = str(request.args.get("status") or "").strip().lower() or None
    if status and status not in _DELIVERY_STATUSES:
        return {"message": f"Unsupported delivery status: {status}"}, 400
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 500)
    except (TypeError, ValueError):
        return {"message": "limit must be an integer"}, 400
    deliveries = MessageHubService.instance().list_deliveries(status=status, limit=limit)
    return [delivery.to_dict() for delivery in deliveries]


@message_hub_blueprint.route("/gateways", methods=["GET"])
@require_auth_or_service_key
def list_gateways():
    return [gateway.to_dict() for gateway in MessageHubService.instance().get_gateways()]


@message_hub_blueprint.route("/inbox/summary", methods=["GET"])
@require_auth_or_service_key
def get_inbox_summary():
    recipient_key = str(request.args.get("recipient_key") or "").strip()
    if not recipient_key:
        return {"message": "recipient_key is required"}, 400
    return MessageHubService.instance().get_inbox_summary(recipient_key)


@message_hub_blueprint.route("/inbox/prepare", methods=["POST"])
@require_service_key
def prepare_inbox():
    data = request.get_json(silent=True) or {}
    recipient_key = str(data.get("recipient_key") or "").strip()
    if not recipient_key:
        return {"message": "recipient_key is required"}, 400
    try:
        limit = min(max(int(data.get("limit", 5)), 1), 10)
    except (TypeError, ValueError):
        return {"message": "limit must be an integer"}, 400
    return MessageHubService.instance().prepare_inbox(
        recipient_key,
        source_type=str(data.get("source_type") or "").strip() or None,
        source_label=str(data.get("source_label") or "").strip() or None,
        limit=limit,
    )


@message_hub_blueprint.route("/inbox/ack", methods=["POST"])
@require_service_key
def acknowledge_inbox():
    data = request.get_json(silent=True) or {}
    recipient_key = str(data.get("recipient_key") or "").strip()
    delivery_ids = data.get("delivery_ids")
    if not recipient_key or not isinstance(delivery_ids, list):
        return {"message": "recipient_key and delivery_ids are required"}, 400
    try:
        ids = [int(item) for item in delivery_ids]
    except (TypeError, ValueError):
        return {"message": "delivery_ids must contain integers"}, 400
    count = MessageHubService.instance().acknowledge_inbox(recipient_key, ids)
    return {"acknowledged": count}


@message_hub_blueprint.route("/stats", methods=["GET"])
@require_auth_or_service_key
def get_queue_stats():
    return MessageHubService.instance().get_queue_stats()


def _delivery_action(delivery_id: int, action: str):
    service = MessageHubService.instance()
    handler = {
        "retry": service.retry_delivery,
        "retry-anyway": service.retry_delivery_anyway,
        "release": service.release_delivery,
        "cancel": service.cancel_delivery,
    }[action]
    delivery = handler(delivery_id)
    if delivery is None:
        past_tense = {
            "retry": "retried",
            "retry-anyway": "retried",
            "release": "released",
            "cancel": "cancelled",
        }[action]
        return {"message": f"Delivery cannot be {past_tense} from its current state"}, 409
    return delivery.to_dict()


@message_hub_blueprint.route("/deliveries/<int:delivery_id>/retry", methods=["POST"])
@require_admin
def retry_delivery(delivery_id: int):
    return _delivery_action(delivery_id, "retry")


@message_hub_blueprint.route("/deliveries/<int:delivery_id>/retry-anyway", methods=["POST"])
@require_admin
def retry_delivery_anyway(delivery_id: int):
    return _delivery_action(delivery_id, "retry-anyway")


@message_hub_blueprint.route("/deliveries/<int:delivery_id>/release", methods=["POST"])
@require_admin
def release_delivery(delivery_id: int):
    return _delivery_action(delivery_id, "release")


@message_hub_blueprint.route("/deliveries/<int:delivery_id>/cancel", methods=["POST"])
@require_admin
def cancel_delivery(delivery_id: int):
    return _delivery_action(delivery_id, "cancel")


@message_hub_blueprint.route("/gateways", methods=["POST"])
@require_admin
def save_gateway():
    data = request.get_json(silent=True) or {}
    key = str(data.get("key") or "").strip().lower()
    name = str(data.get("name") or "").strip()
    gateway_type = str(data.get("type") or "").strip().lower()
    config = data.get("config") or {}
    if not _GATEWAY_KEY.fullmatch(key):
        return {"message": "invalid gateway key"}, 400
    if not name:
        return {"message": "name is required"}, 400
    if gateway_type not in _GATEWAY_TYPES:
        return {"message": f"unsupported gateway type: {gateway_type}"}, 400
    if not isinstance(config, dict):
        return {"message": "config must be an object"}, 400
    try:
        gateway = MessageHubService.instance().save_gateway(
            gateway_id=int(data.get("id") or 0),
            key=key,
            name=name,
            gateway_type=gateway_type,
            enabled=bool(data.get("enabled", True)),
            config=config,
        )
    except KeyError as exc:
        return {"message": str(exc)}, 404
    except (TypeError, ValueError) as exc:
        return {"message": str(exc)}, 400
    return gateway.to_dict(include_config=True)


@message_hub_blueprint.route("/gateways/<string:key>/enabled", methods=["PATCH"])
@require_admin
def set_gateway_enabled(key: str):
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("enabled"), bool):
        return {"message": "enabled must be a boolean"}, 400
    gateway = MessageHubService.instance().set_gateway_enabled(key, data["enabled"])
    if gateway is None:
        return {"message": "Gateway not found"}, 404
    return gateway.to_dict()

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime

from flask import Blueprint, g, request

from src.auth import (
    require_admin,
    require_admin_or_service_key,
    require_auth_or_service_key,
    require_service_key,
)
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
_GATEWAY_TYPES = {"sms", "telegram", "messenger", "reticulum", "webhook"}
_BULK_DELIVERY_ACTIONS = {"acknowledge", "cancel", "release", "retry"}


def _admin_actor() -> dict:
    payload = getattr(g, "jwt_payload", {}) or {}
    raw_user_id = payload.get("sub")
    try:
        user_id = int(raw_user_id) if raw_user_id is not None else None
    except (TypeError, ValueError):
        user_id = None
    return {
        "actor_user_id": user_id,
        "actor_username": str(payload.get("username") or "").strip() or None,
    }


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


def _optional_datetime(name: str) -> datetime | None:
    value = str(request.args.get(name) or "").strip()
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


@message_hub_blueprint.route("/deliveries/search", methods=["GET"])
@require_auth_or_service_key
def search_deliveries():
    try:
        filters = _delivery_search_filters()
    except (TypeError, ValueError) as exc:
        return {"message": str(exc) or "Invalid delivery search filters"}, 400
    return MessageHubService.instance().search_deliveries(**filters)


def _delivery_search_filters() -> dict:
    raw_statuses = str(request.args.get("statuses") or "").strip().lower()
    statuses = [item.strip() for item in raw_statuses.split(",") if item.strip()]
    unsupported = sorted(set(statuses) - _DELIVERY_STATUSES)
    if unsupported:
        raise ValueError(f"Unsupported delivery status: {unsupported[0]}")
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 25)), 1), 100)
    created_after = _optional_datetime("created_after")
    created_before = _optional_datetime("created_before")

    query = str(request.args.get("query") or "").strip()
    recipient = str(request.args.get("recipient") or "").strip()
    source_type = str(request.args.get("source_type") or "").strip()
    source_label = str(request.args.get("source_label") or "").strip()
    source_label_exact = str(request.args.get("source_label_exact") or "").strip()
    conversation_key = None
    if "conversation_key" in request.args:
        conversation_key = str(request.args.get("conversation_key") or "").strip()
    sort = str(request.args.get("sort") or "desc").strip().lower()
    if any((
        len(query) > 200,
        len(recipient) > 500,
        len(source_type) > 100,
        len(source_label) > 300,
        len(source_label_exact) > 300,
        len(conversation_key or "") > 300,
    )):
        raise ValueError("Search filters are too long")
    if sort not in {"asc", "desc"}:
        raise ValueError("sort must be asc or desc")
    return {
        "statuses": statuses or None,
        "gateway_key": str(request.args.get("gateway_key") or "").strip() or None,
        "recipient": recipient or None,
        "query": query or None,
        "created_after": created_after,
        "created_before": created_before,
        "source_type": source_type or None,
        "source_label": source_label or None,
        "source_label_exact": source_label_exact or None,
        "conversation_key": conversation_key,
        "sort": sort,
        "page": page,
        "page_size": page_size,
    }


@message_hub_blueprint.route("/delivery-groups/search", methods=["GET"])
@require_auth_or_service_key
def search_delivery_groups():
    try:
        filters = _delivery_search_filters()
    except (TypeError, ValueError) as exc:
        return {"message": str(exc) or "Invalid delivery group filters"}, 400
    return MessageHubService.instance().search_delivery_groups(**filters)


@message_hub_blueprint.route("/deliveries/<int:delivery_id>", methods=["GET"])
@require_admin_or_service_key
def get_delivery_details(delivery_id: int):
    details = MessageHubService.instance().get_delivery_details(delivery_id)
    if details is None:
        return {"message": "Delivery not found"}, 404
    return details


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


@message_hub_blueprint.route("/deliveries/bulk-action", methods=["POST"])
@require_admin
def bulk_update_deliveries():
    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip().lower()
    delivery_ids = data.get("delivery_ids")
    if action not in _BULK_DELIVERY_ACTIONS:
        return {"message": f"Unsupported bulk delivery action: {action}"}, 400
    if not isinstance(delivery_ids, list) or not delivery_ids:
        return {"message": "delivery_ids must be a non-empty list"}, 400
    try:
        ids = sorted({int(item) for item in delivery_ids})
    except (TypeError, ValueError):
        return {"message": "delivery_ids must contain integers"}, 400
    if any(item <= 0 for item in ids):
        return {"message": "delivery_ids must contain positive integers"}, 400
    if len(ids) > 500:
        return {"message": "at most 500 delivery_ids can be updated at once"}, 400
    return MessageHubService.instance().bulk_update_deliveries(
        ids,
        action,
        **_admin_actor(),
    )


@message_hub_blueprint.route("/delivery-groups/bulk-action", methods=["POST"])
@require_admin
def bulk_update_delivery_group():
    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip().lower()
    if action not in _BULK_DELIVERY_ACTIONS:
        return {"message": f"Unsupported bulk delivery action: {action}"}, 400
    statuses = data.get("statuses")
    if not isinstance(statuses, list) or not statuses:
        return {"message": "statuses must be a non-empty list"}, 400
    statuses = sorted({str(item).strip().lower() for item in statuses})
    if any(status not in _DELIVERY_STATUSES for status in statuses):
        return {"message": "statuses contains an unsupported delivery status"}, 400
    required = {
        name: str(data.get(name) or "").strip()
        for name in ("gateway_key", "recipient_key", "source_type", "source_label")
    }
    if any(not value for value in required.values()):
        return {"message": "gateway, recipient, source type, and source label are required"}, 400
    if any(len(value) > 500 for value in required.values()):
        return {"message": "Group identity is too long"}, 400
    query = str(data.get("query") or "").strip()
    conversation_key = str(data.get("conversation_key") or "").strip()
    if len(query) > 200 or len(conversation_key) > 300:
        return {"message": "Group filters are too long"}, 400
    try:
        created_after = _json_datetime(data.get("created_after"), "created_after")
        created_before = _json_datetime(data.get("created_before"), "created_before")
    except ValueError as exc:
        return {"message": str(exc)}, 400
    return MessageHubService.instance().bulk_update_delivery_group(
        action=action,
        statuses=statuses,
        **required,
        conversation_key=conversation_key,
        query=query or None,
        created_after=created_after,
        created_before=created_before,
        **_admin_actor(),
    )


@message_hub_blueprint.route("/deliveries/bulk-filter-action", methods=["POST"])
@require_admin
def bulk_update_matching_deliveries():
    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip().lower()
    if action not in _BULK_DELIVERY_ACTIONS:
        return {"message": f"Unsupported bulk delivery action: {action}"}, 400
    try:
        filters = _json_delivery_filters(data.get("filters"))
        operation_id = data.get("operation_id")
        if operation_id is not None:
            operation_id = int(operation_id)
            if operation_id <= 0:
                raise ValueError("operation_id must be a positive integer")
    except (TypeError, ValueError) as exc:
        return {"message": str(exc) or "Invalid delivery filters"}, 400
    try:
        return MessageHubService.instance().bulk_update_matching_deliveries(
            action=action,
            operation_id=operation_id,
            **filters,
            **_admin_actor(),
        )
    except KeyError as exc:
        return {"message": str(exc)}, 404
    except ValueError as exc:
        return {"message": str(exc)}, 409


@message_hub_blueprint.route("/bulk-operations", methods=["GET"])
@require_admin
def get_bulk_operations():
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except (TypeError, ValueError):
        return {"message": "limit must be an integer"}, 400
    return MessageHubService.instance().get_bulk_operations(limit)


@message_hub_blueprint.route("/bulk-operations/<int:operation_id>/undo", methods=["POST"])
@require_admin
def undo_bulk_operation(operation_id: int):
    try:
        return MessageHubService.instance().undo_bulk_operation(operation_id)
    except KeyError as exc:
        return {"message": str(exc)}, 404
    except ValueError as exc:
        return {"message": str(exc)}, 409


@message_hub_blueprint.route("/bulk-operations/<int:operation_id>/resume", methods=["POST"])
@require_admin
def resume_bulk_operation(operation_id: int):
    try:
        return MessageHubService.instance().resume_bulk_operation(operation_id)
    except KeyError as exc:
        return {"message": str(exc)}, 404
    except ValueError as exc:
        return {"message": str(exc)}, 409


def _json_datetime(value, name: str) -> datetime | None:
    if value is None or value == "":
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def _json_delivery_filters(value) -> dict:
    if not isinstance(value, dict):
        raise ValueError("filters must be an object")
    raw_statuses = value.get("statuses")
    if not isinstance(raw_statuses, list) or not raw_statuses:
        raise ValueError("filters.statuses must be a non-empty list")
    statuses = sorted({str(item).strip().lower() for item in raw_statuses})
    if any(status not in _DELIVERY_STATUSES for status in statuses):
        raise ValueError("filters.statuses contains an unsupported delivery status")

    def optional_text(name: str, limit: int) -> str | None:
        result = str(value.get(name) or "").strip()
        if len(result) > limit:
            raise ValueError(f"filters.{name} is too long")
        return result or None

    conversation_key = None
    if "conversation_key" in value:
        conversation_key = str(value.get("conversation_key") or "").strip()
        if len(conversation_key) > 300:
            raise ValueError("filters.conversation_key is too long")
    return {
        "statuses": statuses,
        "gateway_key": optional_text("gateway_key", 120),
        "recipient": optional_text("recipient", 500),
        "query": optional_text("query", 200),
        "created_after": _json_datetime(value.get("created_after"), "created_after"),
        "created_before": _json_datetime(value.get("created_before"), "created_before"),
        "source_type": optional_text("source_type", 100),
        "source_label": optional_text("source_label", 300),
        "source_label_exact": optional_text("source_label_exact", 300),
        "conversation_key": conversation_key,
    }


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

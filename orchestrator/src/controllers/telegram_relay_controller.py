from __future__ import annotations

import logging
import os
import re

import requests
from flask import Blueprint, request

from src.auth import require_admin, require_auth_or_service_key, require_service_key
from src.models.orchestrator.MessageRelay import MessageRelayEndpoint, MessageRelayRoute
from src.persistence.MessageRelayStorage import MessageRelayStorage
from src.services.core.auth_service import SERVICE_KEY

telegram_relay_blueprint = Blueprint("telegram_relay", __name__)
_storage = MessageRelayStorage()
_logger = logging.getLogger(__name__)
_RELAY_URL = os.environ.get("TELEGRAM_RELAY_URL", "http://telegram-relay:8080")
_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
_SUPPORTED_ENDPOINT_TYPES = {"telegram", "sms", "webhook"}


def _notify_relay() -> bool:
    try:
        response = requests.post(
            f"{_RELAY_URL}/internal/reload",
            headers={"X-Service-Key": SERVICE_KEY or ""},
            timeout=5,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        _logger.warning("Could not notify telegram-relay of config change: %s", exc)
        return False


def _validate_key(value: object) -> str:
    key = str(value or "").strip().lower()
    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError("key must contain only lowercase letters, numbers and hyphens")
    return key


def _activation_response(payload: dict, runtime_applied: bool) -> tuple[dict, int]:
    payload["runtime_applied"] = runtime_applied
    return payload, 200 if runtime_applied else 202


@telegram_relay_blueprint.route("/endpoints", methods=["GET"])
@require_auth_or_service_key
def list_message_endpoints():
    try:
        return [endpoint.to_dict() for endpoint in _storage.get_endpoints()]
    except Exception as exc:
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/endpoints", methods=["POST"])
@require_admin
def save_message_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        data["key"] = _validate_key(data.get("key"))
        endpoint_type = str(data.get("type") or "").strip().lower()
        if endpoint_type not in _SUPPORTED_ENDPOINT_TYPES:
            return {"message": f"Unsupported endpoint type: {endpoint_type}", "status": 400}, 400
        if not str(data.get("name") or "").strip():
            return {"message": "Missing required field: name", "status": 400}, 400
        endpoint_id = int(data.get("id") or 0)
        if endpoint_id:
            existing = _storage.get_endpoint(endpoint_id)
            if existing is None:
                return {"message": "Endpoint not found", "status": 404}, 404
            if existing.key != data["key"]:
                return {"message": "Endpoint keys cannot be changed", "status": 400}, 400
        if not data.get("capabilities"):
            data["capabilities"] = ["source"] if endpoint_type == "telegram" else ["target"]
        endpoint = _storage.save_endpoint(MessageRelayEndpoint.from_dict(data))
        return _activation_response(endpoint.to_dict(), _notify_relay())
    except ValueError as exc:
        return {"message": str(exc), "status": 400}, 400
    except KeyError as exc:
        return {"message": str(exc), "status": 404}, 404
    except Exception as exc:
        _logger.exception("Could not save message endpoint")
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/endpoints/<int:endpoint_id>", methods=["DELETE"])
@require_admin
def delete_message_endpoint(endpoint_id: int):
    try:
        if not _storage.delete_endpoint(endpoint_id):
            return {"message": "Endpoint not found", "status": 404}, 404
        return _activation_response({"message": "Endpoint deleted"}, _notify_relay())
    except Exception as exc:
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/routes", methods=["GET"])
@require_auth_or_service_key
def list_message_routes():
    try:
        return [route.to_dict() for route in _storage.get_routes()]
    except Exception as exc:
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/routes", methods=["POST"])
@require_admin
def save_message_route():
    try:
        data = request.get_json(silent=True) or {}
        data["key"] = _validate_key(data.get("key"))
        if not str(data.get("name") or "").strip():
            return {"message": "Missing required field: name", "status": 400}, 400
        route_id = int(data.get("id") or 0)
        if route_id:
            existing = _storage.get_route(route_id)
            if existing is None:
                return {"message": "Route not found", "status": 404}, 404
            if existing.key != data["key"]:
                return {"message": "Route keys cannot be changed", "status": 400}, 400
        if not data.get("match_all_sources") and not data.get("source_endpoint_ids"):
            return {"message": "Choose at least one source endpoint", "status": 400}, 400
        if not data.get("targets"):
            return {"message": "Choose at least one target endpoint", "status": 400}, 400
        if data.get("filter") is not None and not isinstance(data["filter"], dict):
            return {"message": "filter must be a JSON object", "status": 400}, 400
        route = _storage.save_route(MessageRelayRoute.from_dict(data))
        return _activation_response(route.to_dict(), _notify_relay())
    except ValueError as exc:
        return {"message": str(exc), "status": 400}, 400
    except KeyError as exc:
        return {"message": str(exc), "status": 404}, 404
    except Exception as exc:
        _logger.exception("Could not save message route")
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/routes/<string:route_key>/enabled", methods=["PATCH"])
@require_auth_or_service_key
def set_message_route_enabled(route_key: str):
    try:
        data = request.get_json(silent=True) or {}
        if "enabled" not in data:
            return {"message": "Missing required field: enabled", "status": 400}, 400
        route = _storage.set_route_enabled(route_key, bool(data["enabled"]))
        if route is None:
            return {"message": "Route not found", "status": 404}, 404
        return _activation_response(route.to_dict(), _notify_relay())
    except Exception as exc:
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route(
    "/routes/<string:route_key>/targets/<string:endpoint_key>/enabled",
    methods=["PATCH"],
)
@require_auth_or_service_key
def set_message_route_target_enabled(route_key: str, endpoint_key: str):
    try:
        data = request.get_json(silent=True) or {}
        if "enabled" not in data:
            return {"message": "Missing required field: enabled", "status": 400}, 400
        route = _storage.set_target_enabled(route_key, endpoint_key, bool(data["enabled"]))
        if route is None:
            return {"message": "Route target not found", "status": 404}, 404
        return _activation_response(route.to_dict(), _notify_relay())
    except Exception as exc:
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/routes/preset/enabled", methods=["PATCH"])
@require_auth_or_service_key
def toggle_preset_routes_enabled():
    data = request.get_json(silent=True) or {}
    if "enabled" not in data:
        return {"message": "Missing required field: enabled", "status": 400}, 400
    try:
        _storage.set_preset_enabled(bool(data["enabled"]))
        return _activation_response({"message": "Preset routes updated"}, _notify_relay())
    except Exception as exc:
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/routes/<int:route_id>", methods=["DELETE"])
@require_admin
def delete_message_route(route_id: int):
    try:
        if not _storage.delete_route(route_id):
            return {"message": "Route not found", "status": 404}, 404
        return _activation_response({"message": "Route deleted"}, _notify_relay())
    except Exception as exc:
        return {"message": str(exc), "status": 500}, 500


@telegram_relay_blueprint.route("/config", methods=["GET"])
@require_service_key
def get_config():
    try:
        return {
            "endpoints": [endpoint.to_dict() for endpoint in _storage.get_endpoints()],
            "routes": [route.to_dict() for route in _storage.get_routes()],
        }
    except Exception as exc:
        _logger.exception("Could not load Telegram relay configuration")
        return {"message": str(exc), "status": 500}, 500

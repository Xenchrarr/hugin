from __future__ import annotations

import logging
import os

import requests
from flask import Blueprint, request

from src.auth import require_auth, require_admin, require_service_key, require_auth_or_service_key
from src.models.orchestrator.TelegramRelay import TelegramRelayDestination, TelegramRelayRule
from src.persistence.TelegramRelayStorage import TelegramRelayStorage
from src.services.core.auth_service import SERVICE_KEY

telegram_relay_blueprint = Blueprint('telegram_relay', __name__)

_storage = TelegramRelayStorage()
_logger = logging.getLogger(__name__)

_RELAY_URL = os.environ.get("TELEGRAM_RELAY_URL", "http://telegram-relay:8080")


def _notify_relay() -> None:
    """Push a config-reload signal to the telegram-relay service."""
    try:
        resp = requests.post(
            f"{_RELAY_URL}/internal/reload",
            headers={"X-Service-Key": SERVICE_KEY or ""},
            timeout=5,
        )
        _logger.info("Relay config reload: HTTP %d", resp.status_code)
    except Exception as exc:
        _logger.warning("Could not notify telegram-relay of config change: %s", exc)


# ── Destinations ──────────────────────────────────────────────────────────────

@telegram_relay_blueprint.route('/destinations', methods=['GET'])
@require_auth_or_service_key
def list_destinations():
    try:
        destinations = _storage.get_destinations()
        return [d.to_dict() for d in destinations]
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@telegram_relay_blueprint.route('/destinations', methods=['POST'])
@require_admin
def upsert_destination():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400
        if not data.get('name'):
            return {'message': 'Missing required field: name', 'status': 400}, 400
        if not data.get('type'):
            return {'message': 'Missing required field: type', 'status': 400}, 400

        dest = TelegramRelayDestination.from_dict(data)
        if dest.id and dest.id > 0:
            result = _storage.update_destination(dest)
            if result is None:
                return {'message': 'Destination not found', 'status': 404}, 404
        else:
            result = _storage.create_destination(dest)

        _notify_relay()
        return result.to_dict(), 200

    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@telegram_relay_blueprint.route('/destinations/<int:destination_id>', methods=['DELETE'])
@require_admin
def delete_destination(destination_id: int):
    try:
        existing = _storage.get_destination(destination_id)
        if existing is None:
            return {'message': 'Destination not found', 'status': 404}, 404
        _storage.delete_destination(destination_id)
        _notify_relay()
        return {'message': 'Destination deleted', 'status': 200}
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


# ── Rules ─────────────────────────────────────────────────────────────────────

@telegram_relay_blueprint.route('/rules', methods=['GET'])
@require_auth_or_service_key
def list_rules():
    try:
        rules = _storage.get_rules()
        return [r.to_dict() for r in rules]
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@telegram_relay_blueprint.route('/rules', methods=['POST'])
@require_admin
def upsert_rule():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400
        if not data.get('name'):
            return {'message': 'Missing required field: name', 'status': 400}, 400

        rule = TelegramRelayRule.from_dict(data)
        if rule.id and rule.id > 0:
            result = _storage.update_rule(rule)
            if result is None:
                return {'message': 'Rule not found', 'status': 404}, 404
        else:
            result = _storage.create_rule(rule)

        _notify_relay()
        return result.to_dict(), 200

    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@telegram_relay_blueprint.route('/rules/<int:rule_id>/enabled', methods=['PATCH'])
@require_service_key
def toggle_rule_enabled(rule_id: int):
    try:
        data = request.get_json(silent=True)
        if data is None or "enabled" not in data:
            return {'message': 'Missing required field: enabled', 'status': 400}, 400
        existing = _storage.get_rule(rule_id)
        if existing is None:
            return {'message': 'Rule not found', 'status': 404}, 404
        existing.enabled = bool(data["enabled"])
        result = _storage.update_rule(existing)
        _notify_relay()
        return result.to_dict(), 200
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@telegram_relay_blueprint.route('/rules/<int:rule_id>', methods=['DELETE'])
@require_admin
def delete_rule(rule_id: int):
    try:
        existing = _storage.get_rule(rule_id)
        if existing is None:
            return {'message': 'Rule not found', 'status': 404}, 404
        _storage.delete_rule(rule_id)
        _notify_relay()
        return {'message': 'Rule deleted', 'status': 200}
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


# ── Service endpoint for the relay (service-key auth) ─────────────────────────

@telegram_relay_blueprint.route('/config', methods=['GET'])
@require_service_key
def get_config():
    """Returns the full destination + rule config for the relay service to consume."""
    try:
        destinations = _storage.get_destinations()
        rules = _storage.get_rules()
        return {
            'destinations': [d.to_dict() for d in destinations],
            'rules': [r.to_dict() for r in rules],
        }
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500

from __future__ import annotations

from flask import Blueprint, request

from src.auth import require_auth, require_auth_or_service_key
from src.models.orchestrator.IcalSource import IcalSource
from src.persistence.IcalSourceStorage import IcalSourceStorage
from src.api.hugin_core.calendar import get_calendar_agenda

ical_source_blueprint = Blueprint('ical_sources', __name__)

_storage = IcalSourceStorage()


@ical_source_blueprint.route('/list', methods=['GET'])
@require_auth
def list_sources():
    try:
        sources = _storage.list_sources()
        return [s.to_dict() for s in sources]
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500, 'error': str(e)}, 500


@ical_source_blueprint.route('/<int:source_id>', methods=['GET'])
@require_auth
def get_source(source_id: int):
    try:
        source = _storage.get_source(source_id)
        if source is None:
            return {'message': 'ICS source not found', 'status': 404}, 404
        return source.to_dict()
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500, 'error': str(e)}, 500


@ical_source_blueprint.route('/', methods=['POST'])
@require_auth
def create_source():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400
        if not data.get('name'):
            return {'message': 'Missing required field: name', 'status': 400}, 400
        if not data.get('url'):
            return {'message': 'Missing required field: url', 'status': 400}, 400

        source = IcalSource.from_dict(data)
        created = _storage.create_source(source)
        return created.to_dict(), 201
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500, 'error': str(e)}, 500


@ical_source_blueprint.route('/<int:source_id>', methods=['PUT'])
@require_auth
def update_source(source_id: int):
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400

        source = IcalSource.from_dict({**data, 'id': source_id})
        updated = _storage.update_source(source)
        if updated is None:
            return {'message': 'ICS source not found', 'status': 404}, 404
        return updated.to_dict()
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500, 'error': str(e)}, 500


@ical_source_blueprint.route('/<int:source_id>', methods=['DELETE'])
@require_auth
def delete_source(source_id: int):
    try:
        _storage.delete_source(source_id)
        return {'message': 'Deleted'}, 200
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500, 'error': str(e)}, 500


@ical_source_blueprint.route('/agenda', methods=['GET'])
@require_auth_or_service_key
def get_agenda():
    try:
        days_param = request.args.get('days', 7)
        try:
            days = max(1, min(int(days_param), 31))
        except (ValueError, TypeError):
            days = 7

        enabled_sources = _storage.list_enabled_sources()
        if not enabled_sources:
            return {'events': []}

        url_to_source = {s.url: s for s in enabled_sources}
        urls = [s.url for s in enabled_sources]
        events = get_calendar_agenda(urls=urls, days=days)
        for event in events:
            source = url_to_source.get(event.get('source_url', ''))
            event['source_name'] = source.name if source else event.get('calendar_name', '')
            event['source_color'] = source.color if source else '#1976d2'
            event['calendar_name'] = source.name if source else event.get('calendar_name', '')
        return {'events': events}
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500, 'error': str(e)}, 500

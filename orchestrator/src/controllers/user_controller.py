from __future__ import annotations

import json

from flask import Blueprint, request, g

from src.auth import require_auth, require_admin, require_service_key
from src.models.orchestrator.User import User
from src.persistence.UserStorage import UserStorage
from src.services.core import auth_service
from src.services.core import user_command_permission_service

user_blueprint = Blueprint('users', __name__)

_storage = UserStorage()


@user_blueprint.route('/list', methods=['GET'])
@require_admin
def list_users():
    try:
        users = _storage.list_users()
        return [u.to_dict() for u in users]
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/me', methods=['GET'])
@require_auth
def get_me():
    try:
        user_id = int(g.jwt_payload.get('sub'))
        user = _storage.get_user(user_id)
        if user is None:
            return {'message': 'User not found', 'status': 404}, 404
        return user.to_dict()
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/me', methods=['PUT'])
@require_auth
def update_me():
    try:
        user_id = int(g.jwt_payload.get('sub'))
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing JSON body', 'status': 400}, 400

        existing = _storage.get_user(user_id)
        if existing is None:
            return {'message': 'User not found', 'status': 404}, 404

        existing.display_name = data.get('display_name', existing.display_name)
        existing.phone_number = data.get('phone_number', existing.phone_number)
        existing.telegram_user_id = data.get('telegram_user_id', existing.telegram_user_id)
        if 'config' in data:
            existing.config = data['config']

        updated = _storage.update_user(existing)

        new_password = data.get('password')
        if new_password:
            current_password = data.get('current_password', '')
            if not current_password:
                return {'message': 'current_password is required to change password', 'status': 400}, 400
            user_with_hash = _storage.get_user_by_username(existing.username)
            if not auth_service.verify_password(current_password, user_with_hash.password_hash):
                return {'message': 'Current password is incorrect', 'status': 400}, 400
            if len(new_password) < 8:
                return {'message': 'password must be at least 8 characters', 'status': 400}, 400
            updated = _storage.update_password(user_id, auth_service.hash_password(new_password))

        return updated.to_dict()

    except Exception as e:
        error = str(e)
        if 'unique' in error.lower():
            return {'message': 'Phone number or Telegram ID already taken by another user', 'status': 409}, 409
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/<int:user_id>', methods=['GET'])
@require_auth
def get_user(user_id: int):
    try:
        caller_id = int(g.jwt_payload.get('sub'))
        caller_is_admin = g.jwt_payload.get('is_admin', False)
        if not caller_is_admin and caller_id != user_id:
            return {'message': 'Access denied', 'status': 403}, 403
        user = _storage.get_user(user_id)
        if user is None:
            return {'message': 'User not found', 'status': 404}, 404
        return user.to_dict()
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/', methods=['POST'])
@require_admin
def create_user():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing JSON body', 'status': 400}, 400

        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not username:
            return {'message': 'username is required', 'status': 400}, 400
        if not password:
            return {'message': 'password is required', 'status': 400}, 400
        if len(password) < 8:
            return {'message': 'password must be at least 8 characters', 'status': 400}, 400

        user = User.from_dict(data)
        password_hash = auth_service.hash_password(password)
        created = _storage.create_user(user, password_hash)
        return created.to_dict(), 201

    except Exception as e:
        error = str(e)
        if 'unique' in error.lower():
            return {'message': 'Username, phone number, or Telegram ID already exists', 'status': 409}, 409
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/<int:user_id>', methods=['PUT'])
@require_auth
def update_user(user_id: int):
    try:
        caller_id = int(g.jwt_payload.get('sub'))
        caller_is_admin = g.jwt_payload.get('is_admin', False)

        if not caller_is_admin and caller_id != user_id:
            return {'message': 'Access denied', 'status': 403}, 403

        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing JSON body', 'status': 400}, 400

        existing = _storage.get_user(user_id)
        if existing is None:
            return {'message': 'User not found', 'status': 404}, 404

        existing.display_name = data.get('display_name', existing.display_name)
        existing.phone_number = data.get('phone_number', existing.phone_number)
        existing.telegram_user_id = data.get('telegram_user_id', existing.telegram_user_id)
        if 'config' in data:
            existing.config = data['config']

        # Only admin can change is_admin
        if caller_is_admin and 'is_admin' in data:
            existing.is_admin = bool(data['is_admin'])

        updated = _storage.update_user(existing)

        new_password = data.get('password')
        if new_password:
            if len(new_password) < 8:
                return {'message': 'password must be at least 8 characters', 'status': 400}, 400
            updated = _storage.update_password(user_id, auth_service.hash_password(new_password))

        return updated.to_dict()

    except Exception as e:
        error = str(e)
        if 'unique' in error.lower():
            return {'message': 'Phone number or Telegram ID already taken by another user', 'status': 409}, 409
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id: int):
    try:
        deleted = _storage.delete_user(user_id)
        if not deleted:
            return {'message': 'User not found', 'status': 404}, 404
        return {'message': 'User deleted', 'status': 200}
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/lookup', methods=['GET'])
def lookup_user():
    """Resolve a user by channel identifier. Used internally by bots — no auth required."""
    channel = request.args.get('channel', '').strip()
    identifier = request.args.get('identifier', '').strip()

    if not channel or not identifier:
        return {'message': 'channel and identifier query params are required', 'status': 400}, 400

    try:
        user = _storage.lookup_user_by_channel(channel, identifier)
        if user is None:
            return {'message': 'User not found', 'status': 404}, 404
        result = user.to_dict()
        if not user.is_admin:
            result['allowed_commands'] = user_command_permission_service.list_by_user(user.id)
        else:
            result['allowed_commands'] = None  # admin bypasses all permission checks
        return result
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_blueprint.route('/<int:user_id>/service-config', methods=['GET'])
@require_service_key
def get_service_config(user_id: int):
    """Return a user's config dict for internal service-to-service calls. Requires X-Service-Key header."""
    try:
        user = _storage.get_user(user_id)
        if user is None:
            return {'message': 'User not found', 'status': 404}, 404
        return user.config
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500

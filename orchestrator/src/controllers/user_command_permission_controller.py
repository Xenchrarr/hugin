from flask import Blueprint, request, g

from src.auth import require_auth, require_admin
from src.persistence.UserStorage import UserStorage
from src.services.core import user_command_permission_service

user_command_permission_blueprint = Blueprint('user_command_permissions', __name__)

_user_storage = UserStorage()


@user_command_permission_blueprint.route('/<int:user_id>/command_permissions', methods=['GET'])
@require_auth
def list_command_permissions(user_id: int):
    caller_id = int(g.jwt_payload.get('sub'))
    caller_is_admin = g.jwt_payload.get('is_admin', False)
    if not caller_is_admin and caller_id != user_id:
        return {'message': 'Access denied', 'status': 403}, 403

    try:
        permissions = user_command_permission_service.list_by_user(user_id)
        return {'user_id': user_id, 'allowed_commands': permissions}
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_command_permission_blueprint.route('/<int:user_id>/command_permissions', methods=['POST'])
@require_admin
def add_command_permission(user_id: int):
    data = request.get_json(silent=True)
    if not data or not data.get('command_path'):
        return {'message': 'command_path is required', 'status': 400}, 400

    if _user_storage.get_user(user_id) is None:
        return {'message': 'User not found', 'status': 404}, 404

    try:
        user_command_permission_service.add(user_id, data['command_path'])
        return {'message': 'ok'}, 201
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500


@user_command_permission_blueprint.route('/<int:user_id>/command_permissions/<path:command_path>', methods=['DELETE'])
@require_admin
def remove_command_permission(user_id: int, command_path: str):
    try:
        user_command_permission_service.remove(user_id, command_path)
        return {'message': 'ok'}
    except Exception as e:
        return {'message': f'Something went wrong: {e}', 'status': 500}, 500

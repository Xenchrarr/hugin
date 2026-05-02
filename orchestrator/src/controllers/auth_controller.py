from __future__ import annotations

from flask import Blueprint, request

from src.auth import require_auth
from src.persistence.UserStorage import UserStorage
from src.services.core import auth_service

auth_blueprint = Blueprint('auth', __name__)

_storage = UserStorage()


@auth_blueprint.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data:
        return {'message': 'Missing JSON body', 'status': 400}, 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return {'message': 'username and password are required', 'status': 400}, 400

    user = _storage.get_user_by_username(username)
    if user is None or not auth_service.verify_password(password, user.password_hash):
        return {'message': 'Invalid credentials', 'status': 401}, 401

    token = auth_service.create_token(user)
    return {
        'token': token,
        'user': user.to_dict(),
    }

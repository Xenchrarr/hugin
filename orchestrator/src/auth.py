from __future__ import annotations

from functools import wraps

from flask import request, jsonify, g

from src.services.core.auth_service import decode_token, SERVICE_KEY


def require_auth(f):
    """Flask decorator that validates a Bearer JWT token and stores the payload in g.jwt_payload."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"message": "Authorization required", "status": 401}), 401

        token = auth_header[len("Bearer "):]
        payload = decode_token(token)
        if payload is None:
            return jsonify({"message": "Invalid or expired token", "status": 401}), 401

        g.jwt_payload = payload
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Flask decorator that requires a valid JWT with is_admin=True."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"message": "Authorization required", "status": 401}), 401

        token = auth_header[len("Bearer "):]
        payload = decode_token(token)
        if payload is None:
            return jsonify({"message": "Invalid or expired token", "status": 401}), 401
        if not payload.get("is_admin", False):
            return jsonify({"message": "Admin access required", "status": 403}), 403

        g.jwt_payload = payload
        return f(*args, **kwargs)
    return decorated


def require_service_key(f):
    """Flask decorator that validates the X-Service-Key header against the configured SERVICE_KEY."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not SERVICE_KEY:
            return jsonify({"message": "Service authentication not configured", "status": 503}), 503
        key = request.headers.get("X-Service-Key", "")
        if not key or key != SERVICE_KEY:
            return jsonify({"message": "Invalid or missing service key", "status": 401}), 401
        return f(*args, **kwargs)
    return decorated

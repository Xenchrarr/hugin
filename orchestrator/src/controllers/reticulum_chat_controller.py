from __future__ import annotations

import os
from typing import Any

import requests
from flask import Blueprint, request

from src.auth import require_auth
from src.services.core.auth_service import SERVICE_KEY


reticulum_chat_blueprint = Blueprint("reticulum_chat", __name__)
_RELAY_URL = os.environ.get("RETICULUM_RELAY_URL", "http://reticulum-relay:8082").rstrip("/")


def _relay(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> tuple[Any, int]:
    try:
        response = requests.request(
            method,
            f"{_RELAY_URL}{path}",
            params=params,
            json=json,
            headers={"X-Service-Key": SERVICE_KEY or ""},
            timeout=30,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": "The Reticulum relay returned an invalid response"}
        return payload, response.status_code
    except requests.RequestException:
        return {"message": "The Reticulum relay is unavailable"}, 502


@reticulum_chat_blueprint.get("/status")
@require_auth
def status():
    return _relay("GET", "/health")


@reticulum_chat_blueprint.get("/conversations")
@require_auth
def conversations():
    return _relay(
        "GET",
        "/api/reticulum/chat/conversations",
        params={"limit": request.args.get("limit", "100")},
    )


@reticulum_chat_blueprint.get("/conversations/<string:destination_hash>/messages")
@require_auth
def messages(destination_hash: str):
    params = {"limit": request.args.get("limit", "100")}
    before_id = request.args.get("before_id")
    if before_id:
        params["before_id"] = before_id
    return _relay(
        "GET",
        f"/api/reticulum/chat/conversations/{destination_hash}/messages",
        params=params,
    )


@reticulum_chat_blueprint.post("/conversations/<string:destination_hash>/read")
@require_auth
def mark_read(destination_hash: str):
    return _relay(
        "POST", f"/api/reticulum/chat/conversations/{destination_hash}/read", json={}
    )


@reticulum_chat_blueprint.post("/messages")
@require_auth
def send_message():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"message": "Request body must be a JSON object"}, 400
    return _relay("POST", "/api/reticulum/chat/messages", json=data)


@reticulum_chat_blueprint.get("/announces")
@require_auth
def announces():
    params = {"limit": request.args.get("limit", "100")}
    aspect = request.args.get("aspect")
    if aspect:
        params["aspect"] = aspect
    return _relay("GET", "/api/reticulum/announces", params=params)


@reticulum_chat_blueprint.post("/announce")
@require_auth
def announce():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"message": "Request body must be a JSON object"}, 400
    return _relay("POST", "/api/reticulum/announce", json=data)

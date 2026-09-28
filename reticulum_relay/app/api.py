from __future__ import annotations

from flask import Flask, jsonify, request

from app.node import ReticulumNode
from app.routing import RouteDispatcher
from app.state import StateStore


def create_app(
    node: ReticulumNode,
    state: StateStore,
    dispatcher: RouteDispatcher,
    service_key: str,
) -> Flask:
    app = Flask("reticulum-relay")

    @app.before_request
    def authorize():
        if request.path == "/health":
            return None
        if service_key and request.headers.get("X-Service-Key", "") != service_key:
            return jsonify({"message": "Unauthorized"}), 401
        return None

    @app.get("/health")
    def health():
        status = node.status()
        return jsonify(status), 200 if status["ready"] else 503

    @app.post("/internal/reload")
    def reload_config():
        try:
            count = dispatcher.reload()
            return jsonify({"status": "ok", "routes": count})
        except Exception as exc:
            return jsonify({"message": str(exc)}), 500

    @app.get("/api/reticulum/conversations")
    def conversations():
        return jsonify(state.contacts())

    @app.post("/api/reticulum/send")
    def send():
        data = request.get_json(silent=True) or {}
        destination_hash = str(data.get("destination_hash") or "").strip().lower()
        text = str(data.get("text") or "").strip()
        title = str(data.get("title") or "").strip()
        method = str(data.get("delivery_method") or data.get("method") or "direct").lower()
        delivery_token = str(data.get("delivery_token") or "").strip()
        if not destination_hash or not text:
            return jsonify({"message": "Missing destination_hash or text"}), 400
        cached = state.delivery_result(delivery_token) if delivery_token else None
        if cached:
            return jsonify({"status": "accepted", "message_id": cached, "duplicate": True})
        try:
            message_id = node.send(destination_hash, text, title, method)
            state.record_delivery(delivery_token, message_id)
            return jsonify({"status": "accepted", "message_id": message_id}), 202
        except (LookupError, ValueError) as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:
            return jsonify({"message": str(exc)}), 503

    @app.get("/api/reticulum/context/<path:phone>")
    def get_context(phone: str):
        context = state.get_context(phone)
        if context is None:
            return jsonify({"message": "No Reticulum reply context for this phone"}), 404
        return jsonify(context)

    @app.post("/api/reticulum/context")
    def set_context():
        data = request.get_json(silent=True) or {}
        phone = str(data.get("phone") or "").strip()
        destination_hash = str(data.get("destination_hash") or "").strip().lower()
        if not phone or not destination_hash:
            return jsonify({"message": "Missing phone or destination_hash"}), 400
        try:
            node._parse_hash(destination_hash)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        state.set_context(phone, destination_hash)
        return jsonify({"status": "ok"})

    return app


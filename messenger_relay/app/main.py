from __future__ import annotations

import asyncio
import logging
import threading

from flask import Flask, jsonify, request

from app.config import load_config
from app.relay import MessengerRelay

logger = logging.getLogger(__name__)


def _authorized(service_key: str) -> bool:
    return not service_key or request.headers.get("X-Service-Key", "") == service_key


def create_control_app(relay: MessengerRelay, service_key: str) -> Flask:
    app = Flask("messenger-relay-control")

    @app.before_request
    def require_service_key():
        if request.path == "/health":
            return None
        if not _authorized(service_key):
            return jsonify({"message": "Unauthorized"}), 401
        return None

    @app.get("/health")
    def health():
        ready = relay.is_ready()
        return jsonify({"status": "ok" if ready else "starting", "ready": ready}), (
            200 if ready else 503
        )

    @app.post("/internal/reload")
    def reload_config():
        if relay._loop is None:
            return jsonify({"message": "Relay is not running"}), 503
        try:
            future = asyncio.run_coroutine_threadsafe(relay.reload_config(), relay._loop)
            future.result(timeout=30)
            return jsonify({"status": "ok"})
        except Exception as exc:
            logger.exception("Messenger config reload failed")
            return jsonify({"message": str(exc)}), 500

    @app.get("/api/messenger/conversations")
    def conversations():
        return jsonify(relay.get_conversations())

    @app.post("/api/messenger/send")
    def send_message():
        data = request.get_json(silent=True) or {}
        thread_id = str(data.get("thread_id") or "").strip()
        text = str(data.get("text") or "").strip()
        if not thread_id or not text:
            return jsonify({"message": "Missing thread_id or text"}), 400
        try:
            event_id = relay.send_message_from_thread(thread_id, text)
            return jsonify({"status": "ok", "message_id": event_id})
        except KeyError as exc:
            return jsonify({"message": str(exc)}), 404
        except Exception as exc:
            logger.exception("Could not send Messenger message")
            return jsonify({"message": str(exc)}), 500

    @app.get("/api/messenger/context/<path:phone>")
    def get_context(phone: str):
        context = relay.get_context(phone)
        if context is None:
            return jsonify({"message": "No reply context for this phone"}), 404
        return jsonify(context)

    @app.post("/api/messenger/context")
    def set_context():
        data = request.get_json(silent=True) or {}
        phone = str(data.get("phone") or "").strip()
        thread_id = str(data.get("thread_id") or "").strip()
        if not phone or not thread_id:
            return jsonify({"message": "Missing phone or thread_id"}), 400
        try:
            relay.set_context(phone, thread_id)
            return jsonify({"status": "ok"})
        except KeyError as exc:
            return jsonify({"message": str(exc)}), 404

    return app


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    config = load_config()
    relay = MessengerRelay(config)
    app = create_control_app(relay, config.service_key)
    server = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8081, use_reloader=False),
        daemon=True,
        name="messenger-relay-control",
    )
    server.start()
    logger.info("Messenger relay control API listening on :8081")
    await relay.start()


if __name__ == "__main__":
    asyncio.run(main())

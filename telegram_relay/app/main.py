import asyncio
import builtins
import logging
import os
import queue
import threading

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify

from app.api.orchestrator import fetch_config
from app.config import load_telegram_config
from app.destinations import build_destinations
from app.forwarder import TelegramForwarder
from app.rules.engine import RuleEngine
from app.rules.models import Rule

_SERVICE_KEY = os.environ.get("SERVICE_KEY", "")

# Queue used to pass interactive auth codes/passwords from the API endpoint
# into the blocking python-telegram login() call.
_auth_input_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
_original_input = builtins.input


def _patched_input(prompt: str = "") -> str:
    """Replace stdin prompts from python-telegram with queue-backed input."""
    prompt_lower = prompt.lower()
    if "code" in prompt_lower or "password" in prompt_lower:
        logger.info(
            "Waiting for Telegram auth input via POST /internal/auth/code (prompt: %r)", prompt
        )
        return _auth_input_queue.get()
    return _original_input(prompt)


builtins.input = _patched_input

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def _build_rules_and_destinations(raw: dict):
    """Parse raw config dict into destinations map and Rule objects."""
    destinations = build_destinations(raw.get("destinations", []))
    rules = []
    for r in raw.get("rules", []):
        rule_data = {
            "name": r.get("name", "unnamed"),
            "priority": r.get("priority", 100),
            "enabled": bool(r.get("enabled", True)),
            "continue": bool(r.get("continue_on_match", False)),
            "conditions": r.get("conditions"),
            "actions": r.get("actions", []),
        }
        rules.append(Rule.model_validate(rule_data))
    return destinations, rules


def _create_reload_server(forwarder: TelegramForwarder) -> threading.Thread:
    """Run a small Flask server that accepts config-reload pushes from the orchestrator."""
    app = Flask("telegram-relay-control")

    @app.route("/internal/reload", methods=["POST"])
    def reload():
        if _SERVICE_KEY:
            key = request.headers.get("X-Service-Key", "")
            if key != _SERVICE_KEY:
                return jsonify({"message": "Unauthorized"}), 401

        logger.info("Reload triggered via /internal/reload")
        try:
            raw = fetch_config()
            destinations, rules = _build_rules_and_destinations(raw)
        except Exception as exc:
            logger.error("Reload aborted — failed to fetch or parse config: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500
        forwarder.reload_config(destinations, rules)
        return jsonify({"status": "ok", "destinations": len(destinations), "rules": len(rules)})

    @app.route("/internal/auth/code", methods=["POST"])
    def submit_auth_code():
        if _SERVICE_KEY:
            key = request.headers.get("X-Service-Key", "")
            if key != _SERVICE_KEY:
                return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", "")).strip()
        if not code:
            return jsonify({"message": "Missing 'code' field"}), 400
        _auth_input_queue.put(code)
        logger.info("Auth code submitted via /internal/auth/code")
        return jsonify({"status": "ok"})

    @app.route("/api/telegram/conversations", methods=["GET"])
    def get_conversations():
        if _SERVICE_KEY:
            key = request.headers.get("X-Service-Key", "")
            if key != _SERVICE_KEY:
                return jsonify({"message": "Unauthorized"}), 401
        convos = forwarder.get_conversations()
        return jsonify(convos)

    @app.route("/api/telegram/send", methods=["POST"])
    def send_telegram():
        if _SERVICE_KEY:
            key = request.headers.get("X-Service-Key", "")
            if key != _SERVICE_KEY:
                return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        chat_id = data.get("chat_id")
        text = data.get("text", "").strip()
        if not chat_id or not text:
            return jsonify({"message": "Missing chat_id or text"}), 400
        try:
            forwarder.send_message(int(chat_id), text)
            return jsonify({"status": "ok"})
        except Exception as exc:
            logger.error("Failed to send Telegram message: %s", exc)
            return jsonify({"message": str(exc)}), 500

    @app.route("/api/telegram/context/<phone>", methods=["GET"])
    def get_context(phone: str):
        if _SERVICE_KEY:
            key = request.headers.get("X-Service-Key", "")
            if key != _SERVICE_KEY:
                return jsonify({"message": "Unauthorized"}), 401
        ctx = forwarder.get_reply_context(phone)
        if ctx is None:
            return jsonify({"message": "No reply context for this phone"}), 404
        return jsonify(ctx)

    @app.route("/api/telegram/context", methods=["POST"])
    def set_context():
        if _SERVICE_KEY:
            key = request.headers.get("X-Service-Key", "")
            if key != _SERVICE_KEY:
                return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        phone = data.get("phone", "").strip()
        chat_id = data.get("chat_id")
        if not phone or not chat_id:
            return jsonify({"message": "Missing phone or chat_id"}), 400
        forwarder.set_reply_context(phone, int(chat_id))
        return jsonify({"status": "ok"})

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    def _run():
        app.run(host="0.0.0.0", port=8080, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True, name="reload-server")
    return t


async def main() -> None:
    _setup_logging()

    telegram_config = load_telegram_config()

    raw = fetch_config()
    destinations, rules = _build_rules_and_destinations(raw)
    engine = RuleEngine(rules)

    forwarder = TelegramForwarder(telegram_config, engine, destinations)

    reload_thread = _create_reload_server(forwarder)
    reload_thread.start()
    logger.info("Reload server listening on :8080")

    try:
        await forwarder.start()
    finally:
        for dest in forwarder._destinations.values():
            await dest.aclose()


if __name__ == "__main__":
    asyncio.run(main())

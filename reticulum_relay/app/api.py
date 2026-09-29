from __future__ import annotations

from flask import Flask, jsonify, request

from app.chat import ChatStore
from app.node import AnnounceRateLimitError, ReticulumNode
from app.routing import RouteDispatcher
from app.state import StateStore


def create_app(
    node: ReticulumNode,
    state: StateStore,
    dispatcher: RouteDispatcher,
    service_key: str,
    chat: ChatStore | None = None,
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

    @app.get("/api/reticulum/chat/conversations")
    def chat_conversations():
        if not chat:
            return jsonify({"message": "Chat storage is unavailable"}), 503
        try:
            limit = int(request.args.get("limit", 100))
        except (TypeError, ValueError):
            return jsonify({"message": "limit must be an integer"}), 400
        return jsonify(chat.conversations(limit=limit))

    @app.get("/api/reticulum/chat/conversations/<destination_hash>/messages")
    def chat_messages(destination_hash: str):
        if not chat:
            return jsonify({"message": "Chat storage is unavailable"}), 503
        try:
            node._parse_hash(destination_hash)
            limit = int(request.args.get("limit", 100))
            before = request.args.get("before_id")
            before_id = int(before) if before else None
        except (TypeError, ValueError) as exc:
            return jsonify({"message": str(exc)}), 400
        return jsonify(chat.messages(destination_hash.lower(), limit, before_id))

    @app.post("/api/reticulum/chat/conversations/<destination_hash>/read")
    def chat_mark_read(destination_hash: str):
        if not chat:
            return jsonify({"message": "Chat storage is unavailable"}), 503
        try:
            node._parse_hash(destination_hash)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        chat.mark_read(destination_hash.lower())
        return jsonify({"status": "ok"})

    @app.post("/api/reticulum/chat/messages")
    def chat_send():
        if not chat:
            return jsonify({"message": "Chat storage is unavailable"}), 503
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"message": "Request body must be a JSON object"}), 400
        destination_hash = str(data.get("destination_hash") or "").strip().lower()
        text = str(data.get("text") or "").strip()
        title = str(data.get("title") or "").strip()
        method = str(data.get("delivery_method") or "direct").strip().lower()
        client_token = str(data.get("client_token") or "").strip()
        if not destination_hash or not text:
            return jsonify({"message": "Missing destination_hash or text"}), 400
        if len(text.encode("utf-8")) + len(title.encode("utf-8")) > 16384:
            return jsonify({"message": "Message content exceeds 16 KiB"}), 400
        if len(client_token) > 128:
            return jsonify({"message": "client_token exceeds 128 characters"}), 400
        try:
            message_id = node.send(
                destination_hash, text, title, method, client_token=client_token
            )
            return jsonify(chat.message(message_id)), 202
        except (LookupError, ValueError) as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:
            return jsonify({"message": str(exc)}), 503

    @app.get("/api/reticulum/announces")
    def announces():
        if not chat:
            return jsonify({"message": "Announce storage is unavailable"}), 503
        try:
            limit = int(request.args.get("limit", 100))
        except (TypeError, ValueError):
            return jsonify({"message": "limit must be an integer"}), 400
        aspect = str(request.args.get("aspect") or "").strip().lower() or None
        allowed = {"lxmf.delivery", "lxmf.propagation", "nomadnetwork.node", "unknown"}
        if aspect and aspect not in allowed:
            return jsonify({"message": "Unsupported announce aspect"}), 400
        return jsonify(chat.announces(limit, aspect))

    @app.post("/api/reticulum/announce")
    def announce():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"message": "Request body must be a JSON object"}), 400
        try:
            return jsonify(node.announce(str(data.get("target") or "delivery").lower()))
        except AnnounceRateLimitError as exc:
            response = jsonify({"message": str(exc), "retry_after": exc.retry_after})
            response.headers["Retry-After"] = str(exc.retry_after)
            return response, 429
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"message": str(exc)}), 503
        except Exception:
            return jsonify({"message": "Could not send Reticulum announce"}), 503

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

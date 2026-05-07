import asyncio
import logging
import threading

from flask import Flask, request, jsonify

log = logging.getLogger(__name__)

_app = Flask(__name__)
_bot = None
_app_loop: asyncio.AbstractEventLoop | None = None


def set_app_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the bot application's running event loop for cross-thread message sending."""
    global _app_loop
    _app_loop = loop
    log.info("Telegram API: application event loop captured")


def set_bot(bot) -> None:
    """Store the telegram Bot instance for sending proactive messages."""
    global _bot
    _bot = bot


@_app.route('/api/telegram/send', methods=['POST'])
def send_message():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    chat_id = data.get('chat_id')
    message = data.get('message')

    if not chat_id or not message:
        return jsonify({'error': 'Missing chat_id or message'}), 400

    if _bot is None:
        return jsonify({'error': 'Bot not initialized'}), 503

    if _app_loop is None:
        return jsonify({'error': 'Application event loop not ready'}), 503

    try:
        future = asyncio.run_coroutine_threadsafe(
            _bot.send_message(chat_id=chat_id, text=message),
            _app_loop,
        )
        future.result(timeout=30)
        return jsonify({'ok': True})
    except Exception as e:
        log.exception("Failed to send Telegram message to %s", chat_id)
        return jsonify({'error': str(e)}), 500


@_app.route('/api/telegram/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


def start_api_server(bot, port: int = 5060) -> None:
    """Start the Flask Telegram API in a daemon thread."""
    set_bot(bot)
    thread = threading.Thread(
        target=lambda: _app.run(host='0.0.0.0', port=port, use_reloader=False),
        daemon=True,
        name='telegram-api',
    )
    thread.start()
    log.info("Telegram API server started on port %d", port)

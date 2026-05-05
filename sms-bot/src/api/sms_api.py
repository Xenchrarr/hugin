import base64
import logging
import threading

from flask import Flask, request, jsonify

from src.api.orchestrator import OrchestratorClient
from src.sms_handler import SMSHandler

log = logging.getLogger(__name__)

_app = Flask(__name__)
_sms_handler: SMSHandler | None = None


def set_sms_handler(handler: SMSHandler) -> None:
    global _sms_handler
    _sms_handler = handler


@_app.route('/api/sms/send', methods=['POST'])
def send_sms():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    phone = data.get('phone')
    message = data.get('message')

    if not phone or not message:
        return jsonify({'error': 'Missing phone or message'}), 400

    _orchestrator = OrchestratorClient()
    if _orchestrator.lookup_user('sms', phone) is None:
        return jsonify({'error': 'Phone number not registered'}), 403

    if _sms_handler is None:
        return jsonify({'error': 'SMS handler not initialized'}), 503

    try:
        _sms_handler.send_sms(phone, message)
        return jsonify({'ok': True})
    except Exception as e:
        log.exception("Failed to send SMS to %s", phone)
        return jsonify({'error': str(e)}), 500


@_app.route('/api/sms/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@_app.route('/api/sms/mms/send', methods=['POST'])
def send_mms():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    phone = data.get('phone')
    message = data.get('message', '')
    media_data_b64 = data.get('media_data')
    media_mime_type = data.get('media_mime_type', 'image/jpeg')

    if not phone or not media_data_b64:
        return jsonify({'error': 'Missing phone or media_data'}), 400

    _orchestrator = OrchestratorClient()
    if _orchestrator.lookup_user('sms', phone) is None:
        return jsonify({'error': 'Phone number not registered'}), 403

    if _sms_handler is None:
        return jsonify({'error': 'SMS handler not initialized'}), 503

    try:
        media_bytes = base64.b64decode(media_data_b64)
    except Exception:
        return jsonify({'error': 'Invalid base64 media_data'}), 400

    try:
        _sms_handler.send_mms(phone, message, media_bytes, media_mime_type)
        return jsonify({'ok': True})
    except Exception as e:
        log.exception("Failed to send MMS to %s", phone)
        return jsonify({'error': str(e)}), 500

def start_api_server(handler: SMSHandler, port: int = 5050) -> None:
    """Start the Flask SMS API in a daemon thread."""
    set_sms_handler(handler)
    thread = threading.Thread(
        target=lambda: _app.run(host='0.0.0.0', port=port, use_reloader=False),
        daemon=True,
        name='sms-api',
    )
    thread.start()
    log.info("SMS API server started on port %d", port)

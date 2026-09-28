import base64
import binascii
import hmac
import hashlib
import logging
import os
import re
import threading

from flask import Flask, request, jsonify

from src.sms_handler import SMSHandler
from src.call_handler import CallHandler
from src.delivery_ledger import (
    DeliveryLedger,
    DispatchTokenConflict,
    ledger_from_environment,
)

log = logging.getLogger(__name__)

_app = Flask(__name__)
_sms_handler: SMSHandler | None = None
_call_handler: CallHandler | None = None
_delivery_ledger: DeliveryLedger | None = None
_SERVICE_KEY = os.environ.get("SERVICE_KEY", "")
_MMS_UPLOAD_MAX_BYTES = max(
    1024,
    int(os.environ.get("MMS_UPLOAD_MAX_BYTES", str(5 * 1024 * 1024))),
)
_MMS_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif"}
_DELIVERY_TOKEN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_PHONE_NUMBER = re.compile(r"^\+[1-9][0-9]{7,14}$")
_call_request_lock = threading.Lock()


def set_handlers(handler: SMSHandler, call_handler: CallHandler) -> None:
    global _sms_handler, _call_handler
    _sms_handler = handler
    _call_handler = call_handler


def _ledger() -> DeliveryLedger:
    global _delivery_ledger
    if _delivery_ledger is None:
        _delivery_ledger = ledger_from_environment()
    return _delivery_ledger


def _begin_dispatch(token: str, fingerprint: str, kind: str):
    try:
        decision = _ledger().begin(token, fingerprint, kind)
    except DispatchTokenConflict as exc:
        return None, (jsonify({'error': str(exc), 'delivery_state': 'conflict'}), 409)
    if decision.state == "accepted":
        response = dict(decision.response or {'ok': True, 'message_id': token})
        response['duplicate'] = True
        return None, (jsonify(response), 200)
    if decision.state == "uncertain":
        return None, (jsonify({
            'error': decision.error or 'Delivery outcome is uncertain',
            'delivery_state': 'uncertain',
        }), 409)
    if decision.state == "in_progress":
        return None, (jsonify({
            'error': 'Delivery is already in progress',
            'delivery_state': 'in_progress',
        }), 409)
    return decision, None


def _fingerprint(kind: str, phone: str, message: str, media: bytes = b'', mime: str = '') -> str:
    digest = hashlib.sha256()
    for value in (kind, phone, message, mime):
        encoded = value.encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
    digest.update(hashlib.sha256(media).digest())
    return digest.hexdigest()


def _send_failed_response(token: str, label: str):
    uncertain = bool(getattr(_sms_handler, 'last_send_uncertain', False))
    error = f'Modem may have accepted part of the {label}' if uncertain else f'Modem did not accept the {label}'
    _ledger().mark_failed(token, error, uncertain=uncertain)
    return jsonify({
        'error': error,
        'delivery_state': 'uncertain' if uncertain else 'failed',
    }), 409 if uncertain else 503


@_app.route('/api/sms/send', methods=['POST'])
def send_sms():
    supplied_key = request.headers.get("X-Service-Key", "")
    if not _SERVICE_KEY or not hmac.compare_digest(supplied_key, _SERVICE_KEY):
        return jsonify({'error': 'Valid service key required'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    phone = data.get('phone')
    message = data.get('message')
    delivery_token = str(data.get('delivery_token') or '').strip()

    if not phone or not message or not _DELIVERY_TOKEN.fullmatch(delivery_token):
        return jsonify({'error': 'phone, message and a valid delivery_token are required'}), 400

    if _sms_handler is None:
        return jsonify({'error': 'SMS handler not initialized'}), 503

    _, replay = _begin_dispatch(
        delivery_token,
        _fingerprint('sms', str(phone), str(message)),
        'sms',
    )
    if replay:
        return replay

    accepted_by_modem = False
    try:
        if not _sms_handler.send_sms(phone, message):
            return _send_failed_response(delivery_token, 'SMS')
        accepted_by_modem = True
        response = {'ok': True, 'message_id': delivery_token}
        _ledger().mark_accepted(delivery_token, response)
        return jsonify(response)
    except Exception as e:
        log.exception("Failed to send SMS to %s", phone)
        uncertain = accepted_by_modem or bool(
            getattr(_sms_handler, 'last_send_uncertain', False)
        )
        try:
            _ledger().mark_failed(delivery_token, str(e), uncertain=uncertain)
        except Exception:
            log.exception("Failed to persist failed SMS receipt %s", delivery_token)
        return jsonify({
            'error': str(e),
            'delivery_state': 'uncertain' if uncertain else 'failed',
        }), 409 if uncertain else 500


@_app.route('/api/sms/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@_app.route('/api/sms/health/ready', methods=['GET'])
def readiness():
    if _sms_handler is None:
        return jsonify({'ready': False, 'error': 'SMS handler not initialized'}), 503
    result = _sms_handler.get_health()
    return jsonify(result), 200 if result.get('ready') else 503


@_app.route('/api/calls/ring', methods=['POST'])
def ring_call():
    supplied_key = request.headers.get("X-Service-Key", "")
    if not _SERVICE_KEY or not hmac.compare_digest(supplied_key, _SERVICE_KEY):
        return jsonify({'error': 'Valid service key required'}), 401

    data = request.get_json(silent=True) or {}
    phone = str(data.get('phone') or '').strip()
    if not _PHONE_NUMBER.fullmatch(phone):
        return jsonify({'error': 'phone must be in E.164 format, for example +4712345678'}), 400

    try:
        ring_seconds = max(5, min(int(data.get('ring_seconds', 20)), 60))
    except (TypeError, ValueError):
        return jsonify({'error': 'ring_seconds must be a number from 5 to 60'}), 400

    if _call_handler is None:
        return jsonify({'error': 'Call handler not initialized'}), 503
    if not _call_request_lock.acquire(blocking=False):
        return jsonify({'error': 'Another outgoing call is already in progress'}), 409

    token = str(data.get('attempt_token') or '').strip()
    try:
        if token:
            if not _DELIVERY_TOKEN.fullmatch(token):
                return jsonify({'error': 'Invalid attempt_token'}), 400
            _, replay = _begin_dispatch(token, _fingerprint('call', phone, str(ring_seconds)), 'call')
            if replay:
                return replay
        result = _call_handler.ring_call(phone, ring_seconds)
        if token:
            _ledger().mark_accepted(token, result)
    except Exception as exc:
        log.exception("Failed to place ring-only call to %s", phone)
        if token:
            try:
                _ledger().mark_failed(token, str(exc), uncertain=True)
            except Exception:
                log.exception("Failed to persist call receipt %s", token)
        return jsonify({'error': str(exc), 'status': 'failed'}), 503
    finally:
        _call_request_lock.release()

    # A completed attempt can legitimately be busy, unanswered, or rejected.
    # Those are call outcomes rather than gateway failures, so return them to
    # the orchestrator without turning them into an ambiguous HTTP retry.
    return jsonify(result), 200


@_app.route('/api/calls/cancel', methods=['POST'])
def cancel_call():
    supplied_key = request.headers.get("X-Service-Key", "")
    if not _SERVICE_KEY or not hmac.compare_digest(supplied_key, _SERVICE_KEY):
        return jsonify({'error': 'Valid service key required'}), 401
    if _call_handler is None or not _call_handler.cancel():
        return jsonify({'error': 'No active call'}), 409
    return jsonify({'ok': True, 'status': 'cancelling'})


@_app.route('/api/calls/health', methods=['GET'])
def call_health():
    supplied_key = request.headers.get("X-Service-Key", "")
    if not _SERVICE_KEY or not hmac.compare_digest(supplied_key, _SERVICE_KEY):
        return jsonify({'error': 'Valid service key required'}), 401
    if _call_handler is None:
        return jsonify({'ready': False}), 503
    result = _call_handler.voice_health()
    return jsonify(result), 200 if result['ready'] else 503


@_app.route('/api/sms/mms/send', methods=['POST'])
def send_mms():
    supplied_key = request.headers.get("X-Service-Key", "")
    if not _SERVICE_KEY or not hmac.compare_digest(supplied_key, _SERVICE_KEY):
        return jsonify({'error': 'Valid service key required'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    phone = data.get('phone')
    message = data.get('message', '')
    media_data_b64 = data.get('media_data')
    media_mime_type = str(data.get('media_mime_type', 'image/jpeg')).strip().lower()
    delivery_token = str(data.get('delivery_token') or '').strip()

    if not phone or not media_data_b64 or not _DELIVERY_TOKEN.fullmatch(delivery_token):
        return jsonify({'error': 'phone, media_data and a valid delivery_token are required'}), 400

    if media_mime_type not in _MMS_IMAGE_TYPES:
        return jsonify({'error': 'Unsupported media_mime_type'}), 400

    try:
        media_bytes = base64.b64decode(media_data_b64, validate=True)
    except (binascii.Error, ValueError, TypeError):
        return jsonify({'error': 'Invalid base64 media_data'}), 400
    if not media_bytes:
        return jsonify({'error': 'Empty media_data'}), 400
    if len(media_bytes) > _MMS_UPLOAD_MAX_BYTES:
        return jsonify({'error': 'Media exceeds upload size limit'}), 413

    if _sms_handler is None:
        return jsonify({'error': 'SMS handler not initialized'}), 503

    _, replay = _begin_dispatch(
        delivery_token,
        _fingerprint('mms', str(phone), str(message), media_bytes, media_mime_type),
        'mms',
    )
    if replay:
        return replay

    accepted_by_modem = False
    try:
        if not _sms_handler.send_mms(phone, message, media_bytes, media_mime_type):
            return _send_failed_response(delivery_token, 'MMS')
        accepted_by_modem = True
        response = {'ok': True, 'message_id': delivery_token}
        _ledger().mark_accepted(delivery_token, response)
        return jsonify(response)
    except Exception as e:
        log.exception("Failed to send MMS to %s", phone)
        uncertain = accepted_by_modem or bool(
            getattr(_sms_handler, 'last_send_uncertain', False)
        )
        try:
            _ledger().mark_failed(delivery_token, str(e), uncertain=uncertain)
        except Exception:
            log.exception("Failed to persist failed MMS receipt %s", delivery_token)
        return jsonify({
            'error': str(e),
            'delivery_state': 'uncertain' if uncertain else 'failed',
        }), 409 if uncertain else 500

def start_api_server(handler: SMSHandler, call_handler: CallHandler, port: int = 5050) -> None:
    """Start the Flask SMS API in a daemon thread."""
    _ledger()
    set_handlers(handler, call_handler)
    thread = threading.Thread(
        target=lambda: _app.run(host='0.0.0.0', port=port, use_reloader=False),
        daemon=True,
        name='sms-api',
    )
    thread.start()
    log.info("SMS API server started on port %d", port)

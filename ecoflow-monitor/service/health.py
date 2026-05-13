import logging
import threading

from flask import Flask, jsonify

log = logging.getLogger(__name__)

_app = Flask(__name__)


@_app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


def start_health_server(port: int = 5080) -> None:
    t = threading.Thread(
        target=lambda: _app.run(host='0.0.0.0', port=port, use_reloader=False),
        daemon=True,
    )
    t.start()
    log.info("Health server started on port %d", port)

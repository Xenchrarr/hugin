from __future__ import annotations

import logging
import signal
import threading
import time

from app.api import create_app
from app.config import Config
from app.node import ReticulumNode
from app.routing import RouteDispatcher
from app.state import StateStore

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    config = Config.from_env()
    config.ensure_directories()
    state = StateStore(config.state_path)
    dispatcher = RouteDispatcher(
        config.orchestrator_url, config.service_key, config.endpoint_key, state
    )
    node = ReticulumNode(config, state, dispatcher)
    app = create_app(node, state, dispatcher, config.service_key)

    api_thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0", port=config.api_port, use_reloader=False, threaded=True
        ),
        daemon=True,
        name="reticulum-control-api",
    )
    api_thread.start()

    stopping = threading.Event()

    def stop(*_args) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    node.start()
    try:
        try:
            dispatcher.reload()
        except Exception:
            logger.exception("Initial route configuration could not be loaded")
        last_refresh = time.monotonic()
        while not stopping.wait(1):
            if time.monotonic() - last_refresh >= config.config_refresh_seconds:
                try:
                    dispatcher.reload()
                except Exception:
                    logger.exception("Reticulum route refresh failed")
                last_refresh = time.monotonic()
    finally:
        node.stop()


if __name__ == "__main__":
    main()


import logging
import signal
import sys

from service.database import engine
from service.health import start_health_server
from service.models import Base
from service.mqtt_service import MQTTService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def main():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    log.info("Database tables verified/created")

    # Start health check HTTP server
    start_health_server()

    # Start MQTT listener (blocks via loop_forever)
    mqtt = MQTTService()
    mqtt.start()

    # Keep process alive; MQTT runs in a background thread
    def _shutdown(sig, frame):
        log.info("Shutting down…")
        mqtt.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    signal.pause()


if __name__ == "__main__":
    main()

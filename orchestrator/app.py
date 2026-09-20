import logging
import os

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

from src import config, app


log = logging.getLogger(__name__)

if __name__ == "__main__":
    log.info("host: %s, port: %s, debug: %s", config.HOST, config.PORT, config.DEBUG)

    app.run(host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=False, )

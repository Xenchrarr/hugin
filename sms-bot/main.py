import logging
import time

from dotenv import load_dotenv

load_dotenv()

from src.config.logging import setup_logging
from src.sms_handler import SMSHandler
from src.command_processor import CommandProcessor
from src.config.config import ALLOWED_SENDERS

logger = logging.getLogger(__name__)


def main():
    setup_logging()

    sms = SMSHandler()
    processor = CommandProcessor()

    try:
        while True:
            messages = sms.read_messages()
            for msg in messages:
                logger.info("Received SMS from %s: %s", msg.sender, msg.text)

                if msg.sender not in ALLOWED_SENDERS:
                    logger.warning("Unauthorized sender %s. Ignoring.", msg.sender)
                    sms.delete_message(msg.index)
                    continue

                response = processor.process(msg.text, sender=msg.sender)
                sms.send_sms(msg.sender, response)
                sms.delete_message(msg.index)

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Exiting gracefully.")
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
    finally:
        sms.close()


if __name__ == "__main__":
    main()
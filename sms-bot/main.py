import logging
import time

from dotenv import load_dotenv

load_dotenv()

from src.config.logging import setup_logging
from src.sms_handler import SMSHandler
from src.command_processor import CommandProcessor
from src.api.sms_api import start_api_server
from src.models.command_response import CommandResponse

logger = logging.getLogger(__name__)


def main():
    setup_logging()

    sms = SMSHandler()
    processor = CommandProcessor()

    # Start the outbound SMS REST API in a background thread
    start_api_server(sms)

    try:
        while True:
            messages = sms.read_messages()
            for msg in messages:
                logger.info("Received SMS from %s: %s", msg.sender, msg.text)

                response = processor.process(msg.text, sender=msg.sender)
                if isinstance(response, CommandResponse):
                    if response.image_bytes:
                        sms.send_mms(msg.sender, response.text, response.image_bytes, response.image_mime)
                    else:
                        sms.send_sms(msg.sender, response.text)
                elif not response.startswith("OK"):
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


if __name__ == "__main__":
    main()
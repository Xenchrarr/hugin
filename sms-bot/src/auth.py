import hmac
import logging

from src.config.config import SENDER_PINS

logger = logging.getLogger(__name__)


def validate_pin(sender: str, pin: str | None) -> bool:
    expected = SENDER_PINS.get(sender)
    if expected is None:
        logger.warning("No PIN configured for sender %s", sender)
        return False
    if pin is None:
        return False
    return hmac.compare_digest(pin, expected)

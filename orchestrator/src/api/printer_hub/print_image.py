import base64
import logging

from . import session, PRINTER_HUB_URL, PRINTER_HUB_TIMEOUT

log = logging.getLogger(__name__)


def send_print_image(image_bytes: bytes) -> dict:
    url = f"{PRINTER_HUB_URL}/api/print/image"
    log.info("Sending print_image request to %s (%d bytes)", url, len(image_bytes))

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    response = session.post(url, json={"image_b64": image_b64}, timeout=PRINTER_HUB_TIMEOUT)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"print_image failed: {response.status_code}: {response.text}")

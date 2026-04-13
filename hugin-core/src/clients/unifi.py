import logging

import requests

from src.config import settings

logger = logging.getLogger(__name__)


class UnifiClient:
    def __init__(self) -> None:
        self._camera_ip = settings.CAMERA_IP

    def download_image(self) -> bytes | None:
        try:
            url = f"http://{self._camera_ip}/snap.jpeg"
            response = requests.get(url, timeout=(5, 15))

            if response.status_code == 200:
                return response.content
            else:
                logger.error("Failed to download image. Status code: %s", response.status_code)
                return None
        except Exception:
            logger.exception("Error downloading camera image")
            return None

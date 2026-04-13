import logging
import re

import cairosvg
import requests

from src.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://www.yr.no/en/content/{yr_id}/meteogram.svg?mode=dark"


class YrClient:
    def __init__(self) -> None:
        self._yr_id = settings.YR_ID

    def get_weather_image(self, yr_id: str | None = None) -> bytes | None:
        try:
            url = BASE_URL.format(yr_id=yr_id or self._yr_id)
            response = requests.get(url, timeout=(5, 15))

            if response.status_code == 200:
                return self._convert_svg_to_png(response.content)
            else:
                logger.error("Failed to download weather image. Status code: %s", response.status_code)
                return None
        except Exception:
            logger.exception("Error downloading weather image")
            return None

    @staticmethod
    def _convert_svg_to_png(svg_content: bytes) -> bytes | None:
        try:
            svg_str = re.sub(
                r"(\d*\.?\d+)rem",
                lambda m: f"{float(m.group(1)) * 16}px",
                svg_content.decode("utf-8"),
            )
            return cairosvg.svg2png(bytestring=svg_str)
        except Exception:
            logger.exception("Error converting SVG to PNG")
            return None

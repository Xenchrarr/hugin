import logging
from io import BytesIO

import requests

logger = logging.getLogger(__name__)


class HuginCoreClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def _get(self, path: str, **params) -> dict | None:
        try:
            response = requests.get(f"{self._base_url}{path}", params=params, timeout=(5, 15))
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("Core API error: GET %s", path)
            return None

    def _get_image(self, path: str, **params) -> BytesIO | None:
        try:
            response = requests.get(f"{self._base_url}{path}", params=params, timeout=(5, 15))
            response.raise_for_status()
            buf = BytesIO(response.content)
            buf.seek(0)
            return buf
        except Exception:
            logger.exception("Core API error: GET image %s", path)
            return None

    # --- Power ---
    def get_current_power(self) -> dict | None:
        return self._get("/api/power/current")

    def get_power_history(self, hours: float = 1) -> dict | None:
        return self._get("/api/power/history", hours=hours)

    def get_growatt_data(self) -> dict | None:
        return self._get("/api/power/growatt")

    # --- Energy ---
    def get_today_energy(self) -> dict | None:
        return self._get("/api/energy/today")

    def get_last_hour_energy(self) -> dict | None:
        return self._get("/api/energy/hour")

    def get_daily_energy(self, days: int = 30) -> dict | None:
        return self._get("/api/energy/daily", days=days)

    # --- Weather ---
    def get_weather_image(self, location_id: str) -> BytesIO | None:
        return self._get_image(f"/api/weather/{location_id}")

    # --- Charts ---
    def get_daily_chart(self) -> BytesIO | None:
        return self._get_image("/api/charts/daily")

    def get_multiday_chart(self, days: int = 7) -> BytesIO | None:
        return self._get_image("/api/charts/multiday", days=days)

    def get_monthly_chart(self, month: int, year: int) -> BytesIO | None:
        return self._get_image("/api/charts/monthly", month=month, year=year)

    # --- Camera ---
    def get_camera_snapshot(self) -> BytesIO | None:
        return self._get_image("/api/camera/snapshot")

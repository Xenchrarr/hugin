import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class HuginCoreClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def _get(self, path: str, **params) -> dict | None:
        try:
            response = requests.get(f"{self._base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("Core API error: GET %s", path)
            return None

    def _post(self, path: str, json: dict | None = None) -> dict | None:
        try:
            response = requests.post(f"{self._base_url}{path}", json=json or {})
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("Core API error: POST %s", path)
            return None

    def _delete(self, path: str, json: dict | None = None) -> dict | None:
        try:
            response = requests.delete(f"{self._base_url}{path}", json=json or {})
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("Core API error: DELETE %s", path)
            return None

    # --- Home Automation ---
    def trigger_automation(self, entity_id: str, *, variables: Optional[Dict[str, Any]] = None) -> dict | None:
        payload: Dict[str, Any] = {"entity_id": entity_id}
        if variables:
            payload["variables"] = variables
        return self._post("/api/home/trigger", json=payload)

    # --- Energy / Power ---
    def get_today_energy(self) -> dict | None:
        return self._get("/api/energy/today")

    def get_growatt_data(self) -> dict | None:
        return self._get("/api/power/growatt")

    # --- Shopping List ---
    def get_shopping_list(self) -> str | None:
        data = self._get("/api/shopping/list")
        if data is None:
            return None
        return data.get("content")

    def add_to_shopping_list(self, item: str) -> dict | None:
        return self._post("/api/shopping/add", json={"item": item})

    def remove_from_shopping_list(self, item: str) -> bool:
        result = self._delete("/api/shopping/remove", json={"item": item})
        return result is not None and result.get("ok", False)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests


class HomeAssistantApiError(RuntimeError):
    def __init__(self, status_code: int, message: str, response_text: str = ""):
        super().__init__(f"Home Assistant API error {status_code}: {message}\n{response_text}")
        self.status_code = status_code
        self.message = message
        self.response_text = response_text


@dataclass(frozen=True)
class HomeAssistantApi:
    base_url: str
    token: str
    timeout_seconds: int = 10

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def get(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout_seconds)
        if r.status_code >= 400:
            raise HomeAssistantApiError(r.status_code, f"GET {path} failed", r.text)
        return r.json() if r.text else None

    def post(self, path: str, *, json: Optional[Dict[str, Any]] = None) -> Any:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        r = requests.post(url, headers=self._headers(), json=json or {}, timeout=self.timeout_seconds)
        if r.status_code >= 400:
            raise HomeAssistantApiError(r.status_code, f"POST {path} failed", r.text)
        return r.json() if r.text else None

    def health_check(self) -> str:
        data = self.get("/api/")
        return data.get("message", "unknown") if isinstance(data, dict) else str(data)

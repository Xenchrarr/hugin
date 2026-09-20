"""Fetches message endpoints and routes from the orchestrator API."""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

_logger = logging.getLogger(__name__)

_ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_API_URL", "http://orchestrator:6000")
_SERVICE_KEY = os.environ.get("SERVICE_KEY", "")


def _headers() -> dict[str, str]:
    return {"X-Service-Key": _SERVICE_KEY}


def fetch_config() -> dict[str, Any]:
    """Return ``endpoints`` and ``routes`` from the orchestrator.

    Raises on any network or HTTP error so callers can decide whether to apply
    the result — preventing a failed fetch from wiping the live rule engine.
    """
    url = f"{_ORCHESTRATOR_URL}/api/telegram_relay/config"
    resp = requests.get(url, headers=_headers(), timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        detail = (resp.text or "").strip()[:1000]
        raise RuntimeError(
            f"Orchestrator config request failed with HTTP {resp.status_code}: {detail}"
        ) from exc
    return resp.json()

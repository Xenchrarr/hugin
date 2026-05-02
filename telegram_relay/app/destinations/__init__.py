from __future__ import annotations

import logging
from typing import Any

from app.destinations.base import AbstractDestination
from app.destinations.webhook import WebhookAdapter
from app.destinations.sms import SmsAdapter
from app.config import DestinationConfig, RetryConfig

logger = logging.getLogger(__name__)


def build_destinations(raw_destinations: list[dict[str, Any]]) -> dict[str, AbstractDestination]:
    """Build a {id: adapter} map from the raw destination dicts returned by the orchestrator API."""
    result: dict[str, AbstractDestination] = {}
    for raw in raw_destinations:
        if not raw.get("enabled", True):
            continue
        dest_id = str(raw["id"])
        dest_name = raw.get("name", dest_id)
        dest_type = raw.get("type", "")
        config: dict[str, Any] = raw.get("config") or {}

        if dest_type == "webhook":
            retry_raw = config.get("retry", {})
            dest_cfg = DestinationConfig(
                id=dest_id,
                type="webhook",
                url=config.get("url", ""),
                headers=config.get("headers", {}),
                timeout=float(config.get("timeout", 10)),
                retry=RetryConfig(
                    max_attempts=retry_raw.get("max_attempts", 3),
                    backoff_seconds=retry_raw.get("backoff_seconds", 2.0),
                ),
            )
            result[dest_id] = WebhookAdapter(dest_cfg)
        elif dest_type == "sms":
            result[dest_id] = SmsAdapter(dest_id, config)
        else:
            logger.warning("Unknown destination type '%s' for '%s' — skipping", dest_type, dest_name)

    return result

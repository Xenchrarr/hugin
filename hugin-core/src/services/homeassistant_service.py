import logging
from typing import Any, Dict, Optional

from src.clients.homeassistant import HomeAssistantApi
from src.config import settings

logger = logging.getLogger(__name__)


def trigger_automation(entity_id: str, *, variables: Optional[Dict[str, Any]] = None) -> Any:
    api = HomeAssistantApi(
        base_url=settings.HA_URL,
        token=settings.HA_TOKEN,
    )
    payload: Dict[str, Any] = {"entity_id": entity_id}
    if variables:
        payload["variables"] = variables

    logger.info("Triggering automation: %s", entity_id)
    return api.post("/api/services/automation/trigger", json=payload)

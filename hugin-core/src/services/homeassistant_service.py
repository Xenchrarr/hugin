import logging
from typing import Any, Dict, Optional

from src.clients.homeassistant import HomeAssistantApi
from src.config import settings

logger = logging.getLogger(__name__)


def get_api() -> HomeAssistantApi:
    return HomeAssistantApi(
        base_url=settings.HA_URL,
        token=settings.HA_TOKEN,
    )


def trigger_automation(entity_id: str, *, variables: Optional[Dict[str, Any]] = None) -> Any:
    api = get_api()
    payload: Dict[str, Any] = {"entity_id": entity_id}
    if variables:
        payload["variables"] = variables

    domain = entity_id.split(".", 1)[0] if "." in entity_id else "automation"
    service = "trigger" if domain == "automation" else "turn_on"
    logger.info("Triggering %s via %s.%s", entity_id, domain, service)
    return api.post(f"/api/services/{domain}/{service}", json=payload)

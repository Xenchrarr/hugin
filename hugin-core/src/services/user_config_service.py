import logging

import requests

from src.config import settings

log = logging.getLogger(__name__)


def get_primary_user_config() -> dict:
    """Fetch the primary user's config from the orchestrator service.

    Returns the config dict on success. Raises RuntimeError if the request fails.
    """
    if not settings.SERVICE_KEY:
        raise RuntimeError("SERVICE_KEY is not configured")

    url = f"{settings.ORCHESTRATOR_API_URL}/api/users/{settings.PRIMARY_USER_ID}/service-config"
    try:
        response = requests.get(
            url,
            headers={"X-Service-Key": settings.SERVICE_KEY},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach orchestrator: {exc}") from exc

    if response.status_code == 404:
        raise RuntimeError(f"Primary user (id={settings.PRIMARY_USER_ID}) not found in orchestrator")
    if not response.ok:
        raise RuntimeError(
            f"Orchestrator returned {response.status_code} fetching user config"
        )

    return response.json()


def get_user_config(user_id: int) -> dict:
    """Fetch a specific user's config from the orchestrator service."""
    if not settings.SERVICE_KEY:
        raise RuntimeError("SERVICE_KEY is not configured")

    url = f"{settings.ORCHESTRATOR_API_URL}/api/users/{user_id}/service-config"
    try:
        response = requests.get(
            url,
            headers={"X-Service-Key": settings.SERVICE_KEY},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach orchestrator: {exc}") from exc

    if response.status_code == 404:
        raise RuntimeError(f"User (id={user_id}) not found in orchestrator")
    if not response.ok:
        raise RuntimeError(
            f"Orchestrator returned {response.status_code} fetching user config for user {user_id}"
        )

    return response.json()

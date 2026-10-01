from src.api.orchestrator import ORCHESTRATOR_API_URL, session
from src.config import settings


def send_log_message(data: dict) -> None:
    url = f"{ORCHESTRATOR_API_URL}/api/logger/log"

    response = session.post(
        url, json=data, timeout=30,
        headers={"X-Service-Key": settings.SERVICE_KEY},
    )
    return response

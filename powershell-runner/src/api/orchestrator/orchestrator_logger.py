import os

from src.api.orchestrator import ORCHESTRATOR_API_URL, session


def send_log_message(data: dict) -> None:
    url = f"{ORCHESTRATOR_API_URL}/api/logger/log"

    response = session.post(url, json=data, timeout=30,
                            headers={'X-Service-Key': os.environ.get('SERVICE_KEY', '')})
    response.raise_for_status()
    return response


def send_log_batch(data: list[dict]) -> None:
    url = f"{ORCHESTRATOR_API_URL}/api/logger/log/batch"
    response = session.post(url, json=data, timeout=30,
                            headers={'X-Service-Key': os.environ.get('SERVICE_KEY', '')})
    response.raise_for_status()

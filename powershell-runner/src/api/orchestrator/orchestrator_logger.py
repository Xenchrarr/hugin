from src.api.orchestrator import ORCHESTRATOR_API_URL, session


def send_log_message(data: dict) -> None:
    url = f"{ORCHESTRATOR_API_URL}/api/logger/log"

    response = session.post(url, json=data)
    return response

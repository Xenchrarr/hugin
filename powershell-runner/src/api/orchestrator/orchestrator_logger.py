from src.api.orchestrator import ORCHESTRATOR_BASE_URL, session


def send_log_message(data: dict) -> None:
    url = f"{ORCHESTRATOR_BASE_URL}/logger/log"

    response = session.post(url, json=data)
    return response

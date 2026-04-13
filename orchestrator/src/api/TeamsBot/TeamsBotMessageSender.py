import traceback
import requests

from src.api.TeamsBot import TEAMS_WEBHOOK_URL, bot_enabled
from src.persistence.DatabaseLogger import DatabaseLogger


def send_message(message: str):
    logger = DatabaseLogger()

    if not bot_enabled:
        return
    url = TEAMS_WEBHOOK_URL
    try:
        session = requests.Session()
        response = session.post(url, json={"text": message})
        if response.status_code != 200:
            raise Exception(f"Failed to send message: {response.text}")
    except Exception as e:
        stack_trace = traceback.format_exception(e)
        stack_trace_string = '\n'.join(stack_trace)
        logger.log_error(f"Failed to send message: {e}", stack_trace_string)
import os
import requests

from src.persistence.DatabaseLogger import DatabaseLogger


def run_power_aggregation(param: str = ""):
    logger = DatabaseLogger()

    core_url = os.environ.get("CORE_API_URL", "http://hugin-core:5100")
    logger.log_info(f"Triggering power aggregation at {core_url}")

    resp = requests.post(f"{core_url}/api/energy/aggregation/run", timeout=120)
    if resp.status_code == 200:
        result = resp.json()
        logger.log_info(f"Aggregation completed: {result}")
    else:
        raise Exception(f"Power aggregation failed: {resp.status_code}: {resp.text}")

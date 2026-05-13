import logging

from . import session, POWERSHELL_API_ENDPOINT, POWERSHELL_SCRIPT_TIMEOUT, POWERSHELL_LIST_TIMEOUT
from src.persistence.DatabaseLogger import DatabaseLogger
from ...ThreadLocalSingleton import ThreadLocalSingleton

log = logging.getLogger(__name__)



def test_script():
    logger = DatabaseLogger()
    url = f"{POWERSHELL_API_ENDPOINT}/script/run"
    log.info("Will start test_script process: %s", url)

    thread_local = ThreadLocalSingleton.instance().thread_local
    job_run_id = thread_local.job_run_id

    body = {
        "job_run_id": str(job_run_id),
        "script_name": "sample_test.ps1",
        "stop_words": ["error", "fatal"]  # optional
    }
    response = session.post(url, json=body, timeout=POWERSHELL_SCRIPT_TIMEOUT)
    if response.status_code == 200:
        return response.json()
    else:
        logger.log_error(f"Error running script : {response.status_code}: {response.text}", "")
        raise Exception(f"{response.status_code}: {response.text}")


def run_generic_script(script_name: str, params: dict):
    logger = DatabaseLogger()
    url = f"{POWERSHELL_API_ENDPOINT}/script/run"
    log.info("Will start generic script: %s via %s", script_name, url)

    thread_local = ThreadLocalSingleton.instance().thread_local
    job_run_id = thread_local.job_run_id

    body = {
        "job_run_id": str(job_run_id),
        "script_name": script_name,
        "stop_words": ["error", "fatal"],
        "params": params,
    }
    response = session.post(url, json=body, timeout=POWERSHELL_SCRIPT_TIMEOUT)
    if response.status_code == 200:
        result = response.json()
        logger.log_info(f"Script {script_name} completed: {result}")
        return result
    else:
        logger.log_error(f"Error running script {script_name}: {response.status_code}: {response.text}", "")
        raise Exception(f"{response.status_code}: {response.text}")


def list_scripts(folder: str):
    url = f"{POWERSHELL_API_ENDPOINT}/script/list"
    response = session.get(url, params={"folder": folder}, timeout=POWERSHELL_LIST_TIMEOUT)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to list scripts: {response.status_code}: {response.text}")
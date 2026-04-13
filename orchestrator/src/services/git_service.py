
import os
import requests

from src.persistence.DatabaseLogger import DatabaseLogger


def run_git_sync(param: str = ""):
    logger = DatabaseLogger()

    if param == "":
        logger.log_info("No repo name specified, syncing all repos")

    powershell_api = os.environ.get("POWERSHELL_API_ENDPOINT", "http://powershell-runner:6001/api")

    # First refresh the repo list from the database
    logger.log_info("Refreshing repo list from database...")
    refresh_resp = requests.post(f"{powershell_api}/git/refresh", timeout=30)
    if refresh_resp.status_code != 200:
        logger.log_error(f"Failed to refresh repos: {refresh_resp.text}", "")

    # Then sync the specified repo (or all)
    body = {"repo_name": param} if param else {}
    logger.log_info(f"Syncing repo: {param or 'all'}")
    resp = requests.post(f"{powershell_api}/git/sync", json=body, timeout=120)

    if resp.status_code == 200:
        result = resp.json().get('result', {})
        for repo_name, info in result.items():
            if info.get('updated'):
                logger.log_info(f"Repo '{repo_name}' updated: {info.get('old_commit', '?')[:8]} -> {info.get('new_commit', '?')[:8]}")
            else:
                logger.log_info(f"Repo '{repo_name}' already up to date (commit: {info.get('commit', '?')[:8]})")
    else:
        raise Exception(f"Git sync failed: {resp.status_code}: {resp.text}")
import os
import logging

import requests

should_log = (os.environ.get("SHOULD_LOG", False) == 'True')

_git_sync_service = None

ORCHESTRATOR_API_URL = os.environ.get('ORCHESTRATOR_API_URL', '')


def _fetch_repos_from_orchestrator():
    """Fetch enabled git repos from the orchestrator database API."""
    if not ORCHESTRATOR_API_URL:
        return []
    try:
        url = f"{ORCHESTRATOR_API_URL}/api/git_repos/list"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        all_repos = resp.json()
        return [r for r in all_repos if r.get('enabled', True)]
    except Exception as e:
        logging.warning(f"Could not fetch repos from orchestrator: {e}")
        return []


def get_git_sync_service(force_refresh=False):
    global _git_sync_service
    if _git_sync_service is not None and not force_refresh:
        return _git_sync_service

    username = os.environ.get('GIT_USERNAME', '')
    password = os.environ.get('GIT_PASSWORD', '')
    default_branch = os.environ.get('GIT_BRANCH', 'main')

    # Try fetching repos from orchestrator DB first
    db_repos = _fetch_repos_from_orchestrator()

    # Fall back to env var for backward compatibility
    if not db_repos:
        raw = os.environ.get('GIT_REPO_URLS', '')
        if not raw:
            return None
        repo_urls = [u.strip() for u in raw.split(',') if u.strip()]
        if not repo_urls:
            return None

        from src.services.git_sync_service import GitSyncService
        _git_sync_service = GitSyncService(
            repo_urls=repo_urls,
            username=username,
            password=password,
            branch=default_branch,
        )
        return _git_sync_service

    from src.services.git_sync_service import GitSyncService
    _git_sync_service = GitSyncService(
        repo_urls=[],
        username=username,
        password=password,
        branch=default_branch,
    )
    _git_sync_service.reload_repos([
        {'name': r['name'], 'url': r['url'], 'branch': r.get('branch', default_branch)}
        for r in db_repos
    ])
    return _git_sync_service


def refresh_git_sync_service():
    """Re-fetch repos from orchestrator and update the service."""
    return get_git_sync_service(force_refresh=True)
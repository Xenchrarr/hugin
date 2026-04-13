import os
import re
import subprocess

from src.services.log_service import log_info, log_error


SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts')


def _repo_name_from_url(url):
    """Extract repo name from URL: https://gitlab.example.com/org/my-scripts.git -> my-scripts"""
    basename = url.rstrip('/').rsplit('/', 1)[-1]
    if basename.endswith('.git'):
        basename = basename[:-4]
    return basename


class GitSyncService:
    """Manages multiple git repos, each cloned into scripts/<repo-name>/."""

    def __init__(self, repo_urls, username, password, branch='main', scripts_dir=None):
        self.branch = branch
        self.scripts_dir = scripts_dir or SCRIPTS_DIR
        self._username = username
        self._password = password
        self._repos = {}
        for url in repo_urls:
            name = _repo_name_from_url(url)
            self._repos[name] = {
                'url': url,
                'auth_url': self._build_auth_url(url, username, password),
                'path': os.path.join(self.scripts_dir, name),
            }

    @property
    def repo_names(self):
        return list(self._repos.keys())

    def add_repo(self, name, url, branch=None):
        """Add a repo dynamically (e.g. after fetching from orchestrator DB)."""
        repo_branch = branch or self.branch
        self._repos[name] = {
            'url': url,
            'auth_url': self._build_auth_url(url, self._username, self._password),
            'path': os.path.join(self.scripts_dir, name),
            'branch': repo_branch,
        }

    def remove_repo(self, name):
        """Remove a repo from the managed set (does not delete files)."""
        self._repos.pop(name, None)

    def reload_repos(self, repos):
        """Replace all managed repos. repos is a list of dicts with keys: name, url, branch."""
        self._repos = {}
        for r in repos:
            name = r.get('name') or _repo_name_from_url(r['url'])
            branch = r.get('branch') or self.branch
            self._repos[name] = {
                'url': r['url'],
                'auth_url': self._build_auth_url(r['url'], self._username, self._password),
                'path': os.path.join(self.scripts_dir, name),
                'branch': branch,
            }

    @staticmethod
    def _build_auth_url(repo_url, username, password):
        return re.sub(
            r'(https?://)',
            rf'\1{username}:{password}@',
            repo_url,
        )

    def _run_git(self, cwd, *args):
        result = subprocess.run(
            ['git'] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            safe_stderr = self._sanitize(result.stderr)
            raise RuntimeError(f"git {args[0]} failed: {safe_stderr}")
        return result.stdout.strip()

    def _sanitize(self, text):
        return re.sub(r'://[^@]+@', '://***@', text)

    def ensure_cloned(self, repo_name=None):
        repos = self._get_repos(repo_name)
        results = {}
        for name, repo in repos.items():
            branch = repo.get('branch', self.branch)
            git_dir = os.path.join(repo['path'], '.git')
            if os.path.isdir(git_dir):
                log_info(f"Repo '{name}' already cloned, skipping")
                results[name] = False
                continue

            os.makedirs(repo['path'], exist_ok=True)
            log_info(f"Cloning repo '{name}' (branch: {branch})")

            result = subprocess.run(
                ['git', 'clone', '--branch', branch, repo['auth_url'], repo['path']],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                safe_stderr = self._sanitize(result.stderr)
                raise RuntimeError(f"git clone failed for '{name}': {safe_stderr}")

            log_info(f"Repo '{name}' cloned successfully")
            results[name] = True
        return results

    def has_updates(self, repo_name):
        repo = self._repos[repo_name]
        branch = repo.get('branch', self.branch)
        self._run_git(repo['path'], 'fetch', 'origin')
        local = self._run_git(repo['path'], 'rev-parse', 'HEAD')
        remote = self._run_git(repo['path'], 'rev-parse', f'origin/{branch}')
        return local != remote

    def pull(self, repo_name):
        repo = self._repos[repo_name]
        branch = repo.get('branch', self.branch)
        old_commit = self._run_git(repo['path'], 'rev-parse', 'HEAD')
        self._run_git(repo['path'], 'pull', 'origin', branch)
        new_commit = self._run_git(repo['path'], 'rev-parse', 'HEAD')
        updated = old_commit != new_commit
        if updated:
            log_info(f"Repo '{repo_name}' updated: {old_commit[:8]} -> {new_commit[:8]}")
        return {
            'updated': updated,
            'old_commit': old_commit,
            'new_commit': new_commit,
        }

    def sync(self, repo_name=None):
        self.ensure_cloned(repo_name)
        repos = self._get_repos(repo_name)
        results = {}
        for name in repos:
            if not self.has_updates(name):
                commit = self._run_git(repos[name]['path'], 'rev-parse', 'HEAD')
                results[name] = {'updated': False, 'commit': commit}
            else:
                results[name] = self.pull(name)
        return results

    def status(self, repo_name=None):
        repos = self._get_repos(repo_name)
        results = {}
        for name, repo in repos.items():
            git_dir = os.path.join(repo['path'], '.git')
            if not os.path.isdir(git_dir):
                results[name] = {'cloned': False}
                continue

            commit = self._run_git(repo['path'], 'rev-parse', 'HEAD')
            branch = self._run_git(repo['path'], 'rev-parse', '--abbrev-ref', 'HEAD')

            try:
                self._run_git(repo['path'], 'fetch', 'origin')
                repo_branch = repo.get('branch', self.branch)
                remote = self._run_git(repo['path'], 'rev-parse', f'origin/{repo_branch}')
                updates_available = commit != remote
            except RuntimeError:
                updates_available = None

            results[name] = {
                'cloned': True,
                'commit': commit,
                'branch': branch,
                'updates_available': updates_available,
            }
        return results

    def _get_repos(self, repo_name=None):
        if repo_name:
            if repo_name not in self._repos:
                raise ValueError(f"Unknown repo: '{repo_name}'. Available: {self.repo_names}")
            return {repo_name: self._repos[repo_name]}
        return self._repos

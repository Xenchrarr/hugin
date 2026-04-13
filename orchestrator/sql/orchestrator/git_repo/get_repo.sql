SELECT id, name, url, branch, enabled, created, updated
FROM git_repos
WHERE id = %s;

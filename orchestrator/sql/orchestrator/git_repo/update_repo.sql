UPDATE git_repos
SET
    name = %s,
    url = %s,
    branch = %s,
    enabled = %s,
    updated = NOW()
WHERE id = %s;

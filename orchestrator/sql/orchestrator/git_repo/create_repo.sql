INSERT INTO git_repos (name, url, branch, enabled, created, updated)
VALUES (%s, %s, %s, %s, NOW(), NOW())
RETURNING id;

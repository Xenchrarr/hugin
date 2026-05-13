INSERT INTO ical_sources (name, url, enabled, color)
VALUES (%s, %s, %s, %s)
RETURNING id, name, url, enabled, created_at, updated_at, color;

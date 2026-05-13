SELECT id, name, url, enabled, created_at, updated_at, color
FROM ical_sources
WHERE enabled = 1
ORDER BY name ASC;

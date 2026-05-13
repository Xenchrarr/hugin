UPDATE ical_sources
SET name       = %s,
    url        = %s,
    enabled    = %s,
    color      = %s,
    updated_at = NOW()
WHERE id = %s
RETURNING id, name, url, enabled, created_at, updated_at, color;

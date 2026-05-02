UPDATE telegram_relay_destinations
SET name = %s, type = %s, config = %s, enabled = %s, updated_at = NOW()
WHERE id = %s
RETURNING id, name, type, config, enabled, created_at, updated_at

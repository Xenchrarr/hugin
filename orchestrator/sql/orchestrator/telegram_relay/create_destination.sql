INSERT INTO telegram_relay_destinations (name, type, config, enabled)
VALUES (%s, %s, %s, %s)
RETURNING id, name, type, config, enabled, created_at, updated_at

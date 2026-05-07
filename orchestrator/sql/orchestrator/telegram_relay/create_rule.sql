INSERT INTO telegram_relay_rules (name, priority, enabled, continue_on_match, conditions, actions, is_preset)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id, name, priority, enabled, continue_on_match, conditions, actions, is_preset, created_at, updated_at

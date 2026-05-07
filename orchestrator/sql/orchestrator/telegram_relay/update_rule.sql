UPDATE telegram_relay_rules
SET name = %s, priority = %s, enabled = %s, continue_on_match = %s, conditions = %s, actions = %s, is_preset = %s, updated_at = NOW()
WHERE id = %s
RETURNING id, name, priority, enabled, continue_on_match, conditions, actions, is_preset, created_at, updated_at

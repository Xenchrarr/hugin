UPDATE telegram_relay_rules
SET name = %s, priority = %s, enabled = %s, continue_on_match = %s, conditions = %s, actions = %s, updated_at = NOW()
WHERE id = %s
RETURNING id, name, priority, enabled, continue_on_match, conditions, actions, created_at, updated_at

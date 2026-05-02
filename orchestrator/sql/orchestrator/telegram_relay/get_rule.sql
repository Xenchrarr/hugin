SELECT id, name, priority, enabled, continue_on_match, conditions, actions, created_at, updated_at
FROM telegram_relay_rules
WHERE id = %s

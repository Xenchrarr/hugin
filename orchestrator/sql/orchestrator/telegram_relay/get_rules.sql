SELECT id, name, priority, enabled, continue_on_match, conditions, actions, is_preset, created_at, updated_at
FROM telegram_relay_rules
ORDER BY priority ASC

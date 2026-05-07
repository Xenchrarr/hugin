UPDATE telegram_relay_rules
SET enabled = %s, updated_at = NOW()
WHERE is_preset = 1

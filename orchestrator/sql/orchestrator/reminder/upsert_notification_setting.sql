INSERT INTO notification_settings (channel, enabled, config, user_label, updated_at)
VALUES (%s, %s, %s, %s, NOW())
ON CONFLICT (channel, user_label) DO UPDATE
SET enabled = EXCLUDED.enabled,
    config = EXCLUDED.config,
    updated_at = NOW()
RETURNING id, channel, enabled, config, user_label, created_at, updated_at;

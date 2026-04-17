SELECT
    id,
    channel,
    enabled,
    config,
    user_label,
    created_at,
    updated_at
FROM notification_settings
ORDER BY channel, user_label;

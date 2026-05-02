SELECT
    id,
    channel,
    enabled,
    config,
    user_label,
    created_at,
    updated_at,
    user_id
FROM notification_settings
WHERE user_id = %s
  AND enabled = TRUE
ORDER BY channel;

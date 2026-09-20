-- Seed a webhook destination pointing to hugin-core's Deye webhook endpoint,
-- and a preset rule that forwards solar-related Telegram messages to it.

INSERT INTO telegram_relay_destinations (name, type, config, enabled)
SELECT
    'Deye Solar Webhook',
    'webhook',
    jsonb_build_object(
        'url', 'http://hugin-core:5100/api/power/deye/webhook',
        'headers', jsonb_build_object(),
        'timeout', 10.0,
        'retry', jsonb_build_object('max_attempts', 3, 'backoff_seconds', 2.0)
    ),
    1
WHERE NOT EXISTS (
    SELECT 1 FROM telegram_relay_destinations WHERE name = 'Deye Solar Webhook'
);

INSERT INTO telegram_relay_rules (name, priority, enabled, continue_on_match, conditions, actions, is_preset)
SELECT
    'Deye solar query',
    50,
    1,
    0,
    jsonb_build_object(
        'all', jsonb_build_array(jsonb_build_object(
            'field', 'text',
            'op', 'regex',
            'value', E'(?i)\\b(deye|sol(ar)?|solenergi|inverter)\\b'
        ))
    ),
    jsonb_build_array(
        jsonb_build_object('type', 'forward', 'destination', destination.id::text)
    ),
    1
FROM telegram_relay_destinations destination
WHERE destination.id = (
    SELECT id FROM telegram_relay_destinations
    WHERE name = 'Deye Solar Webhook'
    ORDER BY id
    LIMIT 1
)
AND NOT EXISTS (
    SELECT 1 FROM telegram_relay_rules WHERE name = 'Deye solar query'
);

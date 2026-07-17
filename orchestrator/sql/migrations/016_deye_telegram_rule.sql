-- Seed a webhook destination pointing to hugin-core's Deye webhook endpoint,
-- and a preset rule that forwards solar-related Telegram messages to it.

WITH new_dest AS (
    INSERT INTO telegram_relay_destinations (name, type, config, enabled)
    VALUES (
        'Deye Solar Webhook',
        'webhook',
        '{
            "url": "http://hugin-core:5100/api/power/deye/webhook",
            "headers": {},
            "timeout": 10.0,
            "retry": {"max_attempts": 3, "backoff_seconds": 2.0}
        }',
        true
    )
    RETURNING id
)
INSERT INTO telegram_relay_rules (name, priority, enabled, continue_on_match, conditions, actions, is_preset)
SELECT
    'Deye solar query',
    50,
    true,
    false,
    '{"all": [{"field": "text", "op": "regex", "value": "(?i)\\b(deye|sol(ar)?|solenergi|inverter)\\b"}]}',
    json_build_array(
        json_build_object('type', 'forward', 'destination', new_dest.id::text)
    ),
    true
FROM new_dest;

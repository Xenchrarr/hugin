-- The Deye reply starts with "Solar data", which also matched the original
-- broad solar keyword filter.  Because the relay account sees messages from
-- the separate Telegram bot as inbound, that formed a webhook -> bot -> relay
-- feedback loop.  Bot-authored messages must never trigger this responder.
-- /deye itself is handled directly by the bot and is excluded here to avoid a
-- second response through the webhook route.

UPDATE message_relay_routes
SET filter = jsonb_build_object(
        'all', jsonb_build_array(
            jsonb_build_object(
                'field', 'sender_is_bot',
                'op', 'neq',
                'value', true
            ),
            jsonb_build_object(
                'not', jsonb_build_object(
                    'field', 'text',
                    'op', 'regex',
                    'value', E'(?i)^/deye(?:@\\w+)?(?:\\s|$)'
                )
            ),
            -- Fail closed for the known generated reply even if TDLib cannot
            -- resolve the sender's bot metadata during an API outage.
            jsonb_build_object(
                'not', jsonb_build_object(
                    'field', 'text',
                    'op', 'regex',
                    'value', E'(?i)^solar data(?:\\r?\\n|$)'
                )
            ),
            jsonb_build_object(
                'field', 'text',
                'op', 'regex',
                'value', E'(?i)\\b(deye|sol(ar)?|solenergi|inverter)\\b'
            )
        )
    ),
    updated_at = NOW()
WHERE name = 'Deye solar query'
  AND is_preset = 1;

-- Let the webhook wait for the bot API's bounded 30-second result. The old
-- ten-second relay timeout could retry the whole side-effecting webhook while
-- its first Telegram send was still in flight.
UPDATE message_relay_endpoints
SET config = jsonb_set(config, '{timeout}', '60'::jsonb, true),
    updated_at = NOW()
WHERE name = 'Deye Solar Webhook'
  AND type = 'webhook';

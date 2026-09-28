-- Personal-account Messenger PoC transport. Credentials remain in the
-- mautrix-meta/Matrix services and are never stored by the orchestrator.

INSERT INTO message_gateways (key, name, type)
VALUES
    ('messenger-main', 'Messenger account', 'messenger'),
    ('webhook-main', 'Webhook delivery', 'webhook')
ON CONFLICT (key) DO NOTHING;

INSERT INTO message_relay_endpoints
    (key, name, type, enabled, capabilities, config)
VALUES
    ('messenger-main', 'Messenger', 'messenger', 1, '["source"]', '{}')
ON CONFLICT (key) DO NOTHING;

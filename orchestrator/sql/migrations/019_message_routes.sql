-- Transport-independent message routing.
--
-- The old telegram_relay_* tables remain in place during the migration period.
-- Existing destinations and rules are copied into endpoints and routes so the
-- running configuration can move to the new model without manual recreation.

CREATE TABLE IF NOT EXISTS message_relay_endpoints (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,
    enabled SMALLINT NOT NULL DEFAULT 1,
    capabilities JSONB NOT NULL DEFAULT '[]',
    config JSONB NOT NULL DEFAULT '{}',
    legacy_destination_id BIGINT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_relay_routes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    enabled SMALLINT NOT NULL DEFAULT 1,
    match_all_sources SMALLINT NOT NULL DEFAULT 0,
    filter JSONB,
    is_preset SMALLINT NOT NULL DEFAULT 0,
    legacy_rule_id BIGINT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_relay_route_sources (
    route_id BIGINT NOT NULL REFERENCES message_relay_routes(id) ON DELETE CASCADE,
    endpoint_id BIGINT NOT NULL REFERENCES message_relay_endpoints(id) ON DELETE CASCADE,
    PRIMARY KEY (route_id, endpoint_id)
);

CREATE TABLE IF NOT EXISTS message_relay_route_targets (
    route_id BIGINT NOT NULL REFERENCES message_relay_routes(id) ON DELETE CASCADE,
    endpoint_id BIGINT NOT NULL REFERENCES message_relay_endpoints(id) ON DELETE CASCADE,
    enabled SMALLINT NOT NULL DEFAULT 1,
    transform JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (route_id, endpoint_id)
);

CREATE INDEX IF NOT EXISTS message_relay_routes_enabled_idx
    ON message_relay_routes (enabled);

CREATE INDEX IF NOT EXISTS message_relay_targets_endpoint_idx
    ON message_relay_route_targets (endpoint_id);

-- The current Telegram process authenticates through environment variables,
-- so its endpoint deliberately contains no credentials.
INSERT INTO message_relay_endpoints
    (key, name, type, enabled, capabilities, config)
VALUES
    ('telegram-main', 'Telegram', 'telegram', 1, '["source"]', '{}')
ON CONFLICT (key) DO NOTHING;

-- Preserve every configured legacy target. Stable numeric-derived keys avoid
-- relying on editable names and remain valid even when names contain spaces.
INSERT INTO message_relay_endpoints
    (key, name, type, enabled, capabilities, config, legacy_destination_id)
SELECT
    'legacy-destination-' || id,
    name,
    type,
    enabled,
    '["target"]'::jsonb,
    config,
    id
FROM telegram_relay_destinations
WHERE true
ON CONFLICT (legacy_destination_id) DO NOTHING;

-- Each legacy Telegram rule becomes a route sourced from telegram-main.
INSERT INTO message_relay_routes
    (key, name, enabled, match_all_sources, filter, is_preset, legacy_rule_id)
SELECT
    'legacy-rule-' || id,
    name,
    enabled,
    0,
    conditions,
    is_preset,
    id
FROM telegram_relay_rules
WHERE true
ON CONFLICT (legacy_rule_id) DO NOTHING;

INSERT INTO message_relay_route_sources (route_id, endpoint_id)
SELECT route.id, source.id
FROM message_relay_routes route
CROSS JOIN message_relay_endpoints source
WHERE source.key = 'telegram-main'
ON CONFLICT (route_id, endpoint_id) DO NOTHING;

-- Forward actions become independently switchable targets. Action-specific
-- redaction and field selection are retained as the target transform.
INSERT INTO message_relay_route_targets (route_id, endpoint_id, enabled, transform)
SELECT DISTINCT ON (route.id, endpoint.id)
    route.id,
    endpoint.id,
    1,
    action.value - 'type' - 'destination'
FROM telegram_relay_rules legacy_rule
JOIN message_relay_routes route
    ON route.legacy_rule_id = legacy_rule.id
CROSS JOIN LATERAL jsonb_array_elements(legacy_rule.actions) action(value)
JOIN message_relay_endpoints endpoint
    ON endpoint.legacy_destination_id::text = action.value->>'destination'
WHERE action.value->>'type' = 'forward'
ORDER BY route.id, endpoint.id
ON CONFLICT (route_id, endpoint_id) DO NOTHING;

-- Durable, transport-independent message queue.
--
-- A message is the immutable event/content submitted to the hub. Each target
-- gets its own delivery row so one unavailable gateway cannot block another.

CREATE TABLE message_gateways (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,
    enabled SMALLINT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    config JSONB NOT NULL DEFAULT '{}',
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    consecutive_successes INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_checked_at TIMESTAMPTZ,
    last_healthy_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('unknown', 'healthy', 'degraded', 'down', 'disabled'))
);

CREATE TABLE message_hub_messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    direction VARCHAR(20) NOT NULL,
    kind VARCHAR(30) NOT NULL DEFAULT 'text',
    source_gateway_id BIGINT REFERENCES message_gateways(id) ON DELETE SET NULL,
    source_endpoint_id BIGINT REFERENCES message_relay_endpoints(id) ON DELETE SET NULL,
    external_id VARCHAR(300),
    conversation_key VARCHAR(300),
    payload JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    priority SMALLINT NOT NULL DEFAULT 50,
    idempotency_key VARCHAR(400) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CHECK (direction IN ('inbound', 'outbound', 'internal')),
    CHECK (priority BETWEEN 0 AND 100)
);

CREATE UNIQUE INDEX message_hub_external_message_idx
    ON message_hub_messages (source_gateway_id, external_id)
    WHERE source_gateway_id IS NOT NULL AND external_id IS NOT NULL;

CREATE TABLE message_hub_deliveries (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES message_hub_messages(id) ON DELETE CASCADE,
    gateway_id BIGINT NOT NULL REFERENCES message_gateways(id) ON DELETE RESTRICT,
    target_endpoint_id BIGINT REFERENCES message_relay_endpoints(id) ON DELETE SET NULL,
    route_id BIGINT REFERENCES message_relay_routes(id) ON DELETE SET NULL,
    address JSONB NOT NULL DEFAULT '{}',
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    recovery_policy VARCHAR(30) NOT NULL DEFAULT 'replay',
    priority SMALLINT NOT NULL DEFAULT 50,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 8,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_token VARCHAR(64),
    leased_until TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    recovery_notified_at TIMESTAMPTZ,
    last_error TEXT,
    idempotency_key VARCHAR(500) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN (
        'pending', 'leased', 'retry_wait', 'accepted', 'held', 'expired', 'dead', 'cancelled'
    )),
    CHECK (recovery_policy IN ('replay', 'digest_hold', 'inbox_only', 'latest_only')),
    CHECK (priority BETWEEN 0 AND 100),
    CHECK (max_attempts > 0)
);

CREATE INDEX message_hub_delivery_claim_idx
    ON message_hub_deliveries (priority DESC, available_at, created_at)
    WHERE status IN ('pending', 'retry_wait');

CREATE INDEX message_hub_delivery_gateway_idx
    ON message_hub_deliveries (gateway_id, status, created_at);

CREATE INDEX message_hub_delivery_message_idx
    ON message_hub_deliveries (message_id);

CREATE TABLE message_delivery_attempts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    delivery_id BIGINT NOT NULL REFERENCES message_hub_deliveries(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    provider_reference VARCHAR(300),
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (outcome IN ('accepted', 'failed'))
);

CREATE INDEX message_delivery_attempts_delivery_idx
    ON message_delivery_attempts (delivery_id, attempt_number);

CREATE TABLE message_gateway_incidents (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    gateway_id BIGINT NOT NULL REFERENCES message_gateways(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    error TEXT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    down_notification_queued_at TIMESTAMPTZ,
    recovery_notification_queued_at TIMESTAMPTZ,
    CHECK (status IN ('open', 'closed'))
);

CREATE UNIQUE INDEX message_gateway_one_open_incident_idx
    ON message_gateway_incidents (gateway_id)
    WHERE status = 'open';

-- Initial gateways use the existing connector services. Additional gateways
-- can be managed through the database/API as more transports are introduced.
INSERT INTO message_gateways (key, name, type)
VALUES
    ('sms-main', 'SMS modem', 'sms'),
    ('telegram-main', 'Telegram account', 'telegram')
ON CONFLICT (key) DO NOTHING;

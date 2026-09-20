CREATE TABLE IF NOT EXISTS sms_outbox (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    phone_number VARCHAR(30) NOT NULL,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    source_type VARCHAR(30) NOT NULL,
    source_key VARCHAR(200),
    source_label VARCHAR(200),
    idempotency_key VARCHAR(300) UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    summary_notified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days')
);

CREATE INDEX IF NOT EXISTS sms_outbox_pending_phone_idx
    ON sms_outbox (phone_number, created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS sms_outbox_pending_source_idx
    ON sms_outbox (source_type, source_key, created_at)
    WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS sms_service_state (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    consecutive_successes INTEGER NOT NULL DEFAULT 0,
    incident_started_at TIMESTAMPTZ,
    down_alert_sent_at TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ,
    last_ready_at TIMESTAMPTZ,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO sms_service_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

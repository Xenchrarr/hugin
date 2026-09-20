CREATE TABLE IF NOT EXISTS checkins (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phone_number VARCHAR(30) NOT NULL,
    alert_phone VARCHAR(30) NOT NULL,
    deadline TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    escalated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS checkins_active_user_idx
    ON checkins (user_id, deadline) WHERE status = 'active';

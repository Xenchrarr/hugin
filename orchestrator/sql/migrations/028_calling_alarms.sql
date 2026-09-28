CREATE TABLE alarms (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(200) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    schedule_type VARCHAR(20) NOT NULL CHECK (schedule_type IN ('once', 'daily', 'weekdays')),
    scheduled_at TIMESTAMPTZ,
    local_time TIME,
    weekdays SMALLINT[],
    timezone VARCHAR(100) NOT NULL DEFAULT 'Europe/Oslo',
    ring_seconds INTEGER NOT NULL DEFAULT 20 CHECK (ring_seconds BETWEEN 5 AND 60),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 5),
    retry_interval_seconds INTEGER NOT NULL DEFAULT 120 CHECK (retry_interval_seconds BETWEEN 30 AND 3600),
    sms_fallback BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (schedule_type = 'once' AND scheduled_at IS NOT NULL) OR
        (schedule_type IN ('daily', 'weekdays') AND local_time IS NOT NULL)
    )
);

CREATE INDEX alarms_user_idx ON alarms(user_id);
CREATE INDEX alarms_enabled_idx ON alarms(enabled) WHERE enabled;

CREATE TABLE alarm_occurrences (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alarm_id BIGINT NOT NULL REFERENCES alarms(id) ON DELETE CASCADE,
    scheduled_for TIMESTAMPTZ NOT NULL,
    source VARCHAR(30) NOT NULL DEFAULT 'scheduled',
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (alarm_id, scheduled_for)
);

CREATE INDEX alarm_occurrences_alarm_idx ON alarm_occurrences(alarm_id, scheduled_for DESC);
CREATE INDEX alarm_occurrences_pending_idx ON alarm_occurrences(status) WHERE status IN ('pending', 'retrying', 'calling');

CREATE TABLE alarm_attempts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurrence_id BIGINT NOT NULL REFERENCES alarm_occurrences(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    attempt_token VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(30) NOT NULL DEFAULT 'calling',
    uncertain BOOLEAN NOT NULL DEFAULT FALSE,
    diagnostics JSONB NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE (occurrence_id, attempt_number)
);

CREATE INDEX alarm_attempts_occurrence_idx ON alarm_attempts(occurrence_id, attempt_number);

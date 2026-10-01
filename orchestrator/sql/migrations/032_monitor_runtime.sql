CREATE TABLE IF NOT EXISTS monitor_runtime_state (
    monitor_key VARCHAR(120) PRIMARY KEY,
    definition_version INTEGER NOT NULL,
    definition_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    enabled_override BOOLEAN,
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_poll_started_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT NOT NULL DEFAULT '',
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    lease_owner VARCHAR(200),
    lease_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS monitor_observations (
    id UUID PRIMARY KEY,
    monitor_key VARCHAR(120) NOT NULL REFERENCES monitor_runtime_state(monitor_key) ON DELETE CASCADE,
    source_event_id VARCHAR(255) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    correlation_key TEXT,
    signals JSONB NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (monitor_key, source_event_id)
);

CREATE TABLE IF NOT EXISTS monitor_incidents (
    id UUID PRIMARY KEY,
    monitor_key VARCHAR(120) NOT NULL REFERENCES monitor_runtime_state(monitor_key) ON DELETE RESTRICT,
    incident_type VARCHAR(120),
    dedupe_key TEXT NOT NULL,
    correlation_key TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    response_workflow_key VARCHAR(120) NOT NULL,
    response_status VARCHAR(40) NOT NULL DEFAULT 'Pending',
    workflow_run_id UUID NOT NULL UNIQUE,
    workflow_input JSONB NOT NULL DEFAULT '{}'::jsonb,
    dispatch_attempts INTEGER NOT NULL DEFAULT 0,
    dispatch_lease_owner VARCHAR(200),
    dispatch_lease_until TIMESTAMPTZ,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (monitor_key, dedupe_key)
);

CREATE TABLE IF NOT EXISTS monitor_incident_runs (
    incident_id UUID NOT NULL REFERENCES monitor_incidents(id) ON DELETE CASCADE,
    job_run_id UUID NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    attempt INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (incident_id, job_run_id), UNIQUE (job_run_id), UNIQUE (incident_id, attempt)
);

CREATE TABLE IF NOT EXISTS monitor_incident_actions (
    incident_id UUID NOT NULL REFERENCES monitor_incidents(id) ON DELETE CASCADE,
    action_key VARCHAR(120) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'Pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_owner VARCHAR(200),
    lease_until TIMESTAMPTZ,
    output JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB NOT NULL DEFAULT '{}'::jsonb,
    outcome VARCHAR(40) NOT NULL DEFAULT 'succeeded',
    summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (incident_id, action_key)
);

CREATE INDEX IF NOT EXISTS monitor_observations_time_idx ON monitor_observations(monitor_key, occurred_at);
CREATE INDEX IF NOT EXISTS monitor_incidents_pending_idx ON monitor_incidents(response_status, dispatch_lease_until, created_at);
CREATE INDEX IF NOT EXISTS monitor_incidents_type_idx ON monitor_incidents(monitor_key, incident_type, created_at DESC);

CREATE TABLE jobs (
                      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                      name VARCHAR(200),
                      enabled SMALLINT,
                      job_type VARCHAR(120),
                      hour SMALLINT,
                      minute SMALLINT,
                      created TIMESTAMP,
                      updated TIMESTAMP,
                      trigger_action VARCHAR(20),
                      param VARCHAR(2000),
                      weekday VARCHAR(10),
                      description VARCHAR(2000),
                      grouping_value VARCHAR(100),
                      max_concurrent SMALLINT NOT NULL DEFAULT 1 CHECK (max_concurrent > 0),
                      workflow_input JSONB NOT NULL DEFAULT '{}'::jsonb,
                      run_at TIMESTAMPTZ,
                      once_status VARCHAR(20)
);

CREATE TABLE job_runs (
                          id UUID PRIMARY KEY,
                          name VARCHAR(100),
                          start_time TIMESTAMP,
                          end_time TIMESTAMP,
                          status VARCHAR(50),
                          job_type VARCHAR(120),
                          result VARCHAR(2000),
                          job_id BIGINT,
                          parameter VARCHAR(2000),
                          run_by VARCHAR(255),
                          workflow_version INTEGER,
                          workflow_input JSONB NOT NULL DEFAULT '{}'::jsonb,
                          workflow_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
                          last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE job_logs (
                          id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                          job_run_id UUID,
                          log_level VARCHAR(10),
                          created_at TIMESTAMP,
                          message VARCHAR(3000),
                          stack_trace VARCHAR(4000)
);

CREATE INDEX job_logs_idx1
    ON job_logs (job_run_id);

CREATE TABLE workflow_step_runs (
    id UUID PRIMARY KEY,
    job_run_id UUID NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    step_key VARCHAR(64) NOT NULL,
    step_type VARCHAR(120) NOT NULL,
    step_version INTEGER NOT NULL DEFAULT 1,
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt > 0),
    status VARCHAR(50) NOT NULL,
    resolved_input JSONB NOT NULL DEFAULT '{}'::jsonb,
    output JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    UNIQUE (job_run_id, step_key, attempt),
    UNIQUE (job_run_id, id)
);

ALTER TABLE job_logs ADD COLUMN step_run_id UUID;
ALTER TABLE job_logs ADD CONSTRAINT job_logs_workflow_step_run_fk
    FOREIGN KEY (job_run_id, step_run_id)
    REFERENCES workflow_step_runs (job_run_id, id) ON DELETE CASCADE;

CREATE TABLE job_run_files (
    id BIGSERIAL PRIMARY KEY,
    job_run_id UUID NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    step_run_id UUID,
    original_filename VARCHAR(500) NOT NULL,
    storage_path VARCHAR(1000) NOT NULL,
    download_url VARCHAR(1000) NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT job_run_files_step_fk FOREIGN KEY (job_run_id, step_run_id)
        REFERENCES workflow_step_runs (job_run_id, id) ON DELETE CASCADE
);

CREATE TABLE workflows (
    id UUID PRIMARY KEY,
    key VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active_revision_id UUID,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    lock_version INTEGER NOT NULL DEFAULT 1 CHECK (lock_version > 0),
    created_by VARCHAR(255) NOT NULL,
    updated_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE workflow_revisions (
    id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    version INTEGER,
    state VARCHAR(20) NOT NULL CHECK (state IN ('draft', 'published')),
    editor_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    compiled_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by VARCHAR(255) NOT NULL,
    published_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    CHECK ((state = 'draft' AND version IS NULL AND published_at IS NULL)
        OR (state = 'published' AND version IS NOT NULL AND version > 0 AND published_at IS NOT NULL)),
    UNIQUE (workflow_id, version)
);

CREATE UNIQUE INDEX workflow_revisions_one_draft_idx
    ON workflow_revisions(workflow_id) WHERE state = 'draft';
CREATE INDEX workflow_revisions_history_idx
    ON workflow_revisions(workflow_id, version DESC) WHERE state = 'published';

CREATE FUNCTION protect_published_workflow_revision() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.state = 'published' THEN
        RAISE EXCEPTION 'Published workflow revisions are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workflow_revisions_immutable
    BEFORE UPDATE OR DELETE ON workflow_revisions
    FOR EACH ROW EXECUTE FUNCTION protect_published_workflow_revision();

ALTER TABLE workflows ADD CONSTRAINT workflows_active_revision_fk
    FOREIGN KEY (active_revision_id) REFERENCES workflow_revisions(id);
ALTER TABLE jobs ADD COLUMN workflow_revision_id UUID REFERENCES workflow_revisions(id);
CREATE INDEX jobs_workflow_revision_idx ON jobs(workflow_revision_id);

CREATE TABLE monitor_runtime_state (
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

CREATE TABLE monitor_observations (
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

CREATE TABLE monitor_incidents (
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
    workflow_revision_id UUID NOT NULL REFERENCES workflow_revisions(id),
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

CREATE TABLE monitor_incident_runs (
    incident_id UUID NOT NULL REFERENCES monitor_incidents(id) ON DELETE CASCADE,
    job_run_id UUID NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    attempt INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (incident_id, job_run_id), UNIQUE (job_run_id), UNIQUE (incident_id, attempt)
);

CREATE TABLE monitor_incident_actions (
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

CREATE INDEX monitor_observations_time_idx ON monitor_observations(monitor_key, occurred_at);
CREATE INDEX monitor_incidents_pending_idx ON monitor_incidents(response_status, dispatch_lease_until, created_at);
CREATE INDEX monitor_incidents_type_idx ON monitor_incidents(monitor_key, incident_type, created_at DESC);
CREATE INDEX monitor_incidents_workflow_revision_idx ON monitor_incidents(workflow_revision_id);

CREATE TABLE request_log (
                             id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                             job_run_id UUID,
                             area VARCHAR(100),
                             request_data VARCHAR(2000),
                             request_type VARCHAR(100),
                             created TIMESTAMP,
                             response_code SMALLINT,
                             response VARCHAR(4000),
                             function_name VARCHAR(200),
                             api_name VARCHAR(50),
                             description VARCHAR(200)
);

CREATE INDEX request_log_idx1
    ON request_log (job_run_id);


ALTER TABLE job_logs
    ADD CONSTRAINT job_logs_job_run_fk
        FOREIGN KEY (job_run_id) REFERENCES job_runs(id);

ALTER TABLE request_log
    ADD CONSTRAINT request_log_job_run_fk
        FOREIGN KEY (job_run_id) REFERENCES job_runs(id);

ALTER TABLE job_runs
    ADD CONSTRAINT job_runs_job_fk
        FOREIGN KEY (job_id) REFERENCES jobs(id);

CREATE TABLE git_repos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    url VARCHAR(500) NOT NULL,
    branch VARCHAR(100) DEFAULT 'main',
    enabled SMALLINT DEFAULT 1,
    created TIMESTAMP DEFAULT NOW(),
    updated TIMESTAMP DEFAULT NOW()
);

-- Code-defined workflows, durable step execution, run artifacts, concurrency,
-- and one-time schedules. Existing job definitions are intentionally not
-- migrated; they may be recreated against the new workflow catalog.

ALTER TABLE jobs
    ALTER COLUMN job_type TYPE VARCHAR(120),
    ADD COLUMN IF NOT EXISTS max_concurrent SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS workflow_input JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS run_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS once_status VARCHAR(20);

-- This release intentionally does not translate legacy string parameters.
-- Preserve the rows for operator reference and run-history joins, but prevent
-- them from firing until schedules are recreated with typed workflow input.
UPDATE jobs SET enabled = 0;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'jobs_max_concurrent_positive'
    ) THEN
        ALTER TABLE jobs ADD CONSTRAINT jobs_max_concurrent_positive
            CHECK (max_concurrent > 0);
    END IF;
END $$;

ALTER TABLE job_runs
    ALTER COLUMN job_type TYPE VARCHAR(120),
    ADD COLUMN IF NOT EXISTS workflow_version INTEGER,
    ADD COLUMN IF NOT EXISTS workflow_input JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS workflow_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS workflow_step_runs (
    id UUID PRIMARY KEY,
    job_run_id UUID NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    step_key VARCHAR(64) NOT NULL,
    step_type VARCHAR(120) NOT NULL,
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

CREATE TABLE IF NOT EXISTS job_run_files (
    id BIGSERIAL PRIMARY KEY,
    job_run_id UUID NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    step_run_id UUID,
    original_filename VARCHAR(500) NOT NULL,
    storage_path VARCHAR(1000) NOT NULL,
    download_url VARCHAR(1000) NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT job_run_files_step_fk
        FOREIGN KEY (job_run_id, step_run_id)
        REFERENCES workflow_step_runs (job_run_id, id) ON DELETE CASCADE
);

ALTER TABLE job_logs ADD COLUMN IF NOT EXISTS step_run_id UUID;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'job_logs_step_requires_job_run'
    ) THEN
        ALTER TABLE job_logs ADD CONSTRAINT job_logs_step_requires_job_run
            CHECK (step_run_id IS NULL OR job_run_id IS NOT NULL);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'job_logs_workflow_step_run_fk'
    ) THEN
        ALTER TABLE job_logs ADD CONSTRAINT job_logs_workflow_step_run_fk
            FOREIGN KEY (job_run_id, step_run_id)
            REFERENCES workflow_step_runs (job_run_id, id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS workflow_step_runs_job_run_idx
    ON workflow_step_runs (job_run_id, started_at, id);
CREATE INDEX IF NOT EXISTS workflow_step_runs_heartbeat_idx
    ON workflow_step_runs (status, heartbeat_at) WHERE status = 'Started';
CREATE INDEX IF NOT EXISTS job_runs_workflow_version_idx
    ON job_runs (job_type, workflow_version) WHERE workflow_version IS NOT NULL;
CREATE INDEX IF NOT EXISTS job_runs_activity_idx
    ON job_runs (status, last_activity_at) WHERE status = 'Started';
CREATE INDEX IF NOT EXISTS job_logs_job_run_step_idx
    ON job_logs (job_run_id, step_run_id, id);
CREATE INDEX IF NOT EXISTS job_logs_job_run_cursor_idx
    ON job_logs (job_run_id, id);
CREATE INDEX IF NOT EXISTS job_run_files_job_run_idx
    ON job_run_files (job_run_id, uploaded_at, id);
CREATE INDEX IF NOT EXISTS jobs_pending_once_idx
    ON jobs (run_at)
    WHERE trigger_action = 'once_at' AND enabled = 1 AND once_status = 'pending';

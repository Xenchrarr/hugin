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

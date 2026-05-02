CREATE TABLE jobs (
                      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                      name VARCHAR(200),
                      enabled SMALLINT,
                      job_type VARCHAR(40),
                      hour SMALLINT,
                      minute SMALLINT,
                      created TIMESTAMP,
                      updated TIMESTAMP,
                      trigger_action VARCHAR(20),
                      param VARCHAR(2000),
                      weekday VARCHAR(10),
                      description VARCHAR(2000),
                      grouping_value VARCHAR(100)
);

CREATE TABLE job_runs (
                          id UUID PRIMARY KEY,
                          name VARCHAR(100),
                          start_time TIMESTAMP,
                          end_time TIMESTAMP,
                          status VARCHAR(50),
                          job_type VARCHAR(100),
                          result VARCHAR(2000),
                          job_id BIGINT,
                          parameter VARCHAR(2000),
                          run_by VARCHAR(255)
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

CREATE TABLE user_command_permissions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    command_path VARCHAR(100) NOT NULL,
    CONSTRAINT ucp_user_command_unique UNIQUE (user_id, command_path),
    CONSTRAINT ucp_user_fk FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
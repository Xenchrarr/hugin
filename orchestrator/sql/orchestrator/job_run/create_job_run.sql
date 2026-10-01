INSERT INTO job_runs (
    id, name, start_time, status, job_type, result, job_id, parameter,
    run_by, run_by_group, metadata, workflow_version, workflow_input,
    workflow_definition, last_activity_at
)
VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());

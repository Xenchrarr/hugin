SELECT
    id,
    name,
    start_time,
    end_time,
    status,
    job_type,
    result,
    job_id,
    parameter,
    run_by,
    run_by_group,
    metadata,
    workflow_version,
    workflow_input,
    workflow_definition,
    last_activity_at
FROM job_runs
WHERE job_id = %s;

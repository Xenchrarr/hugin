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
    metadata
FROM job_runs
WHERE id = %s;

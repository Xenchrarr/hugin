SELECT
    id,
    job_run_id,
    log_level,
    created_at,
    message,
    stack_trace
FROM job_logs
WHERE job_run_id = %s
ORDER BY id ASC;
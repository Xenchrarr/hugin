SELECT
    id,
    job_run_id,
    step_run_id,
    log_level,
    created_at,
    message,
    stack_trace
FROM job_logs

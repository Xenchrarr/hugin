INSERT INTO job_logs (
    job_run_id,
    step_run_id,
    log_level,
    created_at,
    message,
    stack_trace
)
VALUES (%s, %s, %s, NOW(), %s, %s);

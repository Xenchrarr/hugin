INSERT INTO job_logs (
    job_run_id,
    log_level,
    created_at,
    message,
    stack_trace
)
VALUES (%s, %s, NOW(), %s, %s);
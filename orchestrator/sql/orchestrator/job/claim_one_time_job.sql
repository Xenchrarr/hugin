UPDATE jobs
SET enabled = 0,
    once_status = CASE
        WHEN run_at < CURRENT_TIMESTAMP - make_interval(secs => %s) THEN 'missed'
        ELSE 'dispatched'
    END,
    updated = NOW()
WHERE id = %s AND run_at = %s AND run_at <= CURRENT_TIMESTAMP
  AND trigger_action = 'once_at' AND enabled = 1 AND once_status = 'pending'
RETURNING id, name, enabled, job_type, hour, minute, created, updated,
    trigger_action, param, weekday, description, grouping_value,
    NULL AS last_ran, max_concurrent, workflow_input, run_at, once_status;

WITH active_step AS (
    UPDATE workflow_step_runs
    SET heartbeat_at = NOW()
    WHERE id = %s AND status = 'Started'
    RETURNING job_run_id
)
UPDATE job_runs
SET last_activity_at = NOW()
WHERE id IN (SELECT job_run_id FROM active_step) AND status = 'Started';

UPDATE workflow_step_runs
SET status = %s, output = %s, error = %s, summary = %s,
    completed_at = NOW(), heartbeat_at = NOW()
WHERE id = %s;

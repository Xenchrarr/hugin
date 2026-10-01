UPDATE workflow_step_runs SET status = 'Started', started_at = NOW(),
    heartbeat_at = NOW() WHERE id = %s;

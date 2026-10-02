SELECT id, job_run_id, step_key, step_type, step_version, attempt, status,
       resolved_input, output, error, summary, started_at, completed_at,
       heartbeat_at
FROM workflow_step_runs
WHERE job_run_id = %s
ORDER BY COALESCE(started_at, completed_at) ASC NULLS LAST, id ASC;

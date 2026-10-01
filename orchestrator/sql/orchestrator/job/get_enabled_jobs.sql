SELECT id, name, enabled, job_type, hour, minute, created, updated,
       trigger_action, param, weekday, description, grouping_value,
       NULL AS last_ran, max_concurrent, workflow_input, run_at, once_status
FROM jobs
WHERE enabled = 1;

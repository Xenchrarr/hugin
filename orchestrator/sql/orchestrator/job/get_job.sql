SELECT id, name, enabled, job_type, hour, minute, created, updated,
       trigger_action, param, weekday, description, grouping_value
FROM jobs
WHERE id = %s;
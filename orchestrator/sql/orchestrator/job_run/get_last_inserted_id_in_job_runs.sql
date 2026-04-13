SELECT id
FROM job_runs
WHERE job_type = %s
ORDER BY start_time DESC
LIMIT 1;
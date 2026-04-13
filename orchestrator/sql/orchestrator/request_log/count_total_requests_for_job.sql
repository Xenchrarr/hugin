SELECT COUNT(*) AS total_rows
FROM request_log
WHERE job_run_id = %s;
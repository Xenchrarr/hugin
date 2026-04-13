SELECT COUNT(*) AS total_rows
FROM job_runs runs
INNER JOIN jobs j ON j.id = runs.job_id
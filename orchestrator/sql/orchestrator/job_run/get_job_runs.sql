SELECT
    runs.id,
    runs.name,
    runs.start_time,
    runs.end_time,
    runs.status,
    runs.job_type,
    runs.result,
    runs.job_id,
    runs.parameter,
    runs.run_by,
    runs.run_by_group,
    runs.metadata
FROM job_runs runs
INNER JOIN jobs j ON j.id = runs.job_id
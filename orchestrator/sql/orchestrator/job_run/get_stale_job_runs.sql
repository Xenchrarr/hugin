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
WHERE runs.status = 'Started'
  AND runs.start_time < NOW() - make_interval(mins => %s);

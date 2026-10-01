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
    runs.metadata,
    runs.workflow_version,
    runs.workflow_input,
    runs.workflow_definition,
    runs.last_activity_at
FROM job_runs runs
LEFT JOIN jobs j ON j.id = runs.job_id

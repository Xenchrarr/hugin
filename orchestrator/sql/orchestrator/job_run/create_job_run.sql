INSERT INTO job_runs (
    id, name, start_time, status, job_type, result, job_id, parameter, run_by, run_by_group, metadata
)
VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s);
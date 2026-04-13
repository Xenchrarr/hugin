UPDATE job_runs
SET
    name = %s,
    end_time = NOW(),
    status = %s,
    result = %s,
    job_id = %s
WHERE id = %s;
INSERT INTO workflow_step_runs
    (id, job_run_id, step_key, step_type, step_version, attempt, status, resolved_input)
VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s);

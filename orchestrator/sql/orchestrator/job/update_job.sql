UPDATE jobs
SET
    name = %s,
    enabled = %s,
    job_type = %s,
    hour = %s,
    minute = %s,
    updated = NOW(),
    trigger_action = %s,
    param = %s,
    weekday = %s,
    description = %s,
    grouping_value = %s,
    max_concurrent = %s,
    workflow_input = %s,
    run_at = %s,
    once_status = %s,
    workflow_revision_id = %s
WHERE id = %s;

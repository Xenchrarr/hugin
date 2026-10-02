INSERT INTO jobs (
    name,
    enabled,
    job_type,
    hour,
    minute,
    created,
    trigger_action,
    param,
    weekday,
    description,
    grouping_value,
    max_concurrent,
    workflow_input,
    run_at,
    once_status,
    workflow_revision_id
)
VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id;

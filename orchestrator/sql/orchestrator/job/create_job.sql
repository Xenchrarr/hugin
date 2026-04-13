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
    grouping_value
)
VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
RETURNING id;
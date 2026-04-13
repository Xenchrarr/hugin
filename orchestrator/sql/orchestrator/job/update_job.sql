UPDATE jobs
SET
    name = %s,
    enabled = %s,
    hour = %s,
    minute = %s,
    updated = NOW(),
    trigger_action = %s,
    param = %s,
    weekday = %s,
    description = %s,
    grouping_value = %s
WHERE id = %s;
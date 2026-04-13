SELECT
    j.id,
    j.name,
    j.enabled,
    j.job_type,
    j.hour,
    j.minute,
    j.created,
    j.updated,
    j.trigger_action,
    j.param,
    j.weekday,
    j.description,
    j.grouping_value,
    jr.end_time AS last_ran
FROM jobs j
LEFT JOIN (
    SELECT DISTINCT ON (job_id)
        job_id,
        end_time
    FROM job_runs
    WHERE end_time IS NOT NULL
    ORDER BY job_id, end_time DESC
) jr
    ON jr.job_id = j.id;
SELECT
    r.id,
    r.title,
    r.message,
    r.due_at,
    r.recurrence,
    r.status,
    r.recipient_ids,
    r.created_by,
    r.scheduler_job_id,
    r.created_at,
    r.updated_at,
    r.user_id
FROM reminders r
WHERE r.id = %s

UPDATE reminders
SET title = %s,
    message = %s,
    due_at = %s,
    recurrence = %s,
    status = %s,
    recipient_ids = %s,
    scheduler_job_id = %s,
    updated_at = NOW()
WHERE id = %s
RETURNING id, title, message, due_at, recurrence, status, recipient_ids, created_by, scheduler_job_id, created_at, updated_at;

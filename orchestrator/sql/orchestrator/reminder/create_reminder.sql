INSERT INTO reminders (title, message, due_at, recurrence, status, recipient_ids, created_by, scheduler_job_id, user_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id, title, message, due_at, recurrence, status, recipient_ids, created_by, scheduler_job_id, created_at, updated_at, user_id;

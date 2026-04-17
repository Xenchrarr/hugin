SELECT
    h.id,
    h.reminder_id,
    h.action,
    h.channel,
    h.detail,
    h.created_at
FROM reminder_history h
WHERE h.reminder_id = %s
ORDER BY h.created_at DESC;

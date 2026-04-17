INSERT INTO reminder_history (reminder_id, action, channel, detail)
VALUES (%s, %s, %s, %s)
RETURNING id;

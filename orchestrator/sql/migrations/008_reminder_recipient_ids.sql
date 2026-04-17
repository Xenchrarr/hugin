-- Replace channels (TEXT[]) with recipient_ids (INTEGER[]) referencing notification_settings.id

ALTER TABLE reminders DROP COLUMN IF EXISTS channels;
ALTER TABLE reminders ADD COLUMN recipient_ids INTEGER[] DEFAULT NULL;

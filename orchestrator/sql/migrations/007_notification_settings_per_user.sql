-- Per-user notification settings: allow multiple rows per channel (one per user)

ALTER TABLE notification_settings
    ADD COLUMN user_label VARCHAR(100) NOT NULL DEFAULT '';

ALTER TABLE notification_settings
    DROP CONSTRAINT notification_settings_channel_key;

ALTER TABLE notification_settings
    ADD CONSTRAINT notification_settings_channel_user_key UNIQUE (channel, user_label);

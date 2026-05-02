-- Add users table with direct phone/telegram identifiers for fast bot lookup.
-- Notification settings and reminders gain a user_id FK.

CREATE TABLE users (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username        VARCHAR(100)  UNIQUE NOT NULL,
    display_name    VARCHAR(200),
    phone_number    VARCHAR(30)   UNIQUE,
    telegram_chat_id BIGINT       UNIQUE,
    password_hash   VARCHAR(200)  NOT NULL,
    config          JSONB         NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ   DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   DEFAULT NOW()
);

ALTER TABLE notification_settings
    ADD COLUMN user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE reminders
    ADD COLUMN user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX idx_notification_settings_user_id ON notification_settings(user_id);
CREATE INDEX idx_reminders_user_id             ON reminders(user_id);

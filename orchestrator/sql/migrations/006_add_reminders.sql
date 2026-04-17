-- Reminder system tables

CREATE TABLE notification_settings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel VARCHAR(50) NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE reminders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    message TEXT,
    due_at TIMESTAMPTZ NOT NULL,
    recurrence VARCHAR(100) DEFAULT NULL,
    status VARCHAR(20) DEFAULT 'active',
    channels TEXT[] DEFAULT NULL,
    created_by VARCHAR(50) DEFAULT 'frontend',
    scheduler_job_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX reminders_status_idx ON reminders (status);
CREATE INDEX reminders_due_at_idx ON reminders (due_at);

CREATE TABLE reminder_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reminder_id BIGINT NOT NULL REFERENCES reminders(id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL,
    channel VARCHAR(50),
    detail TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX reminder_history_reminder_idx ON reminder_history (reminder_id);

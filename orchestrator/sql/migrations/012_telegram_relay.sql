-- Telegram Relay configuration tables
-- Destinations and rules previously defined in config.yaml are now stored here.

CREATE TABLE telegram_relay_destinations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,         -- 'webhook' | 'sms'
    config JSONB NOT NULL DEFAULT '{}',
    enabled SMALLINT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE telegram_relay_rules (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    enabled SMALLINT DEFAULT 1,
    continue_on_match SMALLINT DEFAULT 0,
    conditions JSONB,                  -- NULL = catch-all
    actions JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX telegram_relay_rules_priority_idx ON telegram_relay_rules (priority);

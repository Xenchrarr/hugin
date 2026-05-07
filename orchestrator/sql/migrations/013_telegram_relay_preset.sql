ALTER TABLE telegram_relay_rules
    ADD COLUMN is_preset SMALLINT NOT NULL DEFAULT 0;

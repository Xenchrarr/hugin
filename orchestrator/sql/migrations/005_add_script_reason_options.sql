CREATE TABLE IF NOT EXISTS script_reason_options (
    id          BIGSERIAL    PRIMARY KEY,
    script_name VARCHAR(500) NOT NULL,
    option_label VARCHAR(500) NOT NULL,
    display_order SMALLINT   DEFAULT 0,
    created     TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_script_reason_options_script_name
    ON script_reason_options (script_name);

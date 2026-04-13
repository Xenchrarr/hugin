CREATE TABLE IF NOT EXISTS script_permissions (
    id         BIGSERIAL    PRIMARY KEY,
    script_name VARCHAR(500) NOT NULL UNIQUE,
    allowed_for_servicedesk BOOLEAN NOT NULL DEFAULT FALSE,
    created    TIMESTAMP    DEFAULT NOW(),
    updated    TIMESTAMP    DEFAULT NOW()
);

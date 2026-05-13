CREATE TABLE ical_sources (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       VARCHAR(200)  NOT NULL,
    url        TEXT          NOT NULL,
    enabled    SMALLINT      NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

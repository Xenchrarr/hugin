-- Binary message content is stored separately from JSON queue payloads.

CREATE TABLE IF NOT EXISTS message_hub_attachments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id BIGINT NOT NULL
        REFERENCES message_hub_messages(id) ON DELETE CASCADE,
    position SMALLINT NOT NULL DEFAULT 0,
    content_type VARCHAR(120) NOT NULL,
    filename VARCHAR(255),
    content BYTEA NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (message_id, position),
    CHECK (position >= 0),
    CHECK (size_bytes > 0),
    CHECK (size_bytes = octet_length(content))
);

CREATE INDEX IF NOT EXISTS message_hub_attachments_message_idx
    ON message_hub_attachments (message_id, position);

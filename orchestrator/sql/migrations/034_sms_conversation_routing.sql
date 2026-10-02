-- Durable, per-user conversation identities and SMS reply references.
CREATE TABLE sms_routing_conversations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service VARCHAR(30) NOT NULL,
    integration_account VARCHAR(120) NOT NULL,
    external_chat_id VARCHAR(300) NOT NULL,
    alias VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (alias ~ '^[a-z][a-z0-9_-]{0,9}/[a-z0-9][a-z0-9_-]{0,17}$'),
    UNIQUE (owner_user_id, service, integration_account, external_chat_id),
    UNIQUE (owner_user_id, alias)
);

CREATE TABLE sms_routing_reference_counters (
    owner_user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    next_reference BIGINT NOT NULL DEFAULT 1 CHECK (next_reference > 0)
);

CREATE TABLE sms_routing_messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id BIGINT NOT NULL REFERENCES sms_routing_conversations(id) ON DELETE RESTRICT,
    reference BIGINT NOT NULL CHECK (reference > 0),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    body TEXT NOT NULL,
    author VARCHAR(200),
    external_message_id VARCHAR(300),
    transport_event_id VARCHAR(400),
    reply_to_reference BIGINT,
    send_status VARCHAR(20) NOT NULL DEFAULT 'received'
        CHECK (send_status IN ('received', 'prepared', 'accepted', 'queued', 'failed', 'uncertain')),
    status_detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (owner_user_id, reference)
);

CREATE UNIQUE INDEX sms_routing_message_event_idx
    ON sms_routing_messages (owner_user_id, direction, transport_event_id)
    WHERE transport_event_id IS NOT NULL;

CREATE INDEX sms_routing_history_idx
    ON sms_routing_messages (owner_user_id, conversation_id, reference DESC);

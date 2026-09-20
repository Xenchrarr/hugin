-- A queued response can acknowledge held inbox deliveries, but only after the
-- response itself has been accepted by its gateway.

CREATE TABLE IF NOT EXISTS message_delivery_ack_links (
    response_delivery_id BIGINT NOT NULL
        REFERENCES message_hub_deliveries(id) ON DELETE CASCADE,
    held_delivery_id BIGINT NOT NULL
        REFERENCES message_hub_deliveries(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (response_delivery_id, held_delivery_id),
    CHECK (response_delivery_id <> held_delivery_id)
);

CREATE INDEX IF NOT EXISTS message_delivery_ack_links_held_idx
    ON message_delivery_ack_links (held_delivery_id);

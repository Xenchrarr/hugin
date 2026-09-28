-- Durable audit and recovery records for administrator bulk delivery actions.

CREATE TABLE message_hub_bulk_operations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action VARCHAR(20) NOT NULL,
    scope VARCHAR(20) NOT NULL,
    actor_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    actor_username VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'in_progress',
    affected_count INTEGER NOT NULL DEFAULT 0,
    undone_count INTEGER NOT NULL DEFAULT 0,
    filter_snapshot JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    undo_expires_at TIMESTAMPTZ,
    undone_at TIMESTAMPTZ,
    CHECK (action IN ('acknowledge', 'cancel', 'release', 'retry')),
    CHECK (scope IN ('selection', 'filter', 'group')),
    CHECK (status IN ('in_progress', 'completed', 'partially_undone', 'undone')),
    CHECK (affected_count >= 0),
    CHECK (undone_count >= 0 AND undone_count <= affected_count)
);

CREATE INDEX message_hub_bulk_operations_created_idx
    ON message_hub_bulk_operations (created_at DESC);

CREATE TABLE message_hub_bulk_operation_items (
    operation_id BIGINT NOT NULL
        REFERENCES message_hub_bulk_operations(id) ON DELETE CASCADE,
    delivery_id BIGINT NOT NULL,
    previous_status VARCHAR(20) NOT NULL,
    previous_available_at TIMESTAMPTZ NOT NULL,
    previous_last_error TEXT,
    previous_acknowledged_at TIMESTAMPTZ,
    previous_expired_at TIMESTAMPTZ,
    undone_at TIMESTAMPTZ,
    PRIMARY KEY (operation_id, delivery_id)
);

CREATE INDEX message_hub_bulk_operation_items_delivery_idx
    ON message_hub_bulk_operation_items (delivery_id);

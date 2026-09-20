-- Give every physical gateway dispatch a stable identity. Automatic retries keep
-- this token; an operator-forced retry after an ambiguous result rotates it.

ALTER TABLE message_hub_deliveries
    ADD COLUMN dispatch_token VARCHAR(64);

UPDATE message_hub_deliveries
SET dispatch_token = md5(
    id::text || ':' || message_id::text || ':' || clock_timestamp()::text || ':' || random()::text
)
WHERE dispatch_token IS NULL;

ALTER TABLE message_hub_deliveries
    ALTER COLUMN dispatch_token SET NOT NULL,
    ADD CONSTRAINT message_hub_deliveries_dispatch_token_key UNIQUE (dispatch_token),
    DROP CONSTRAINT message_hub_deliveries_status_check,
    ADD CONSTRAINT message_hub_deliveries_status_check CHECK (status IN (
        'pending', 'leased', 'retry_wait', 'accepted', 'held', 'acknowledged',
        'uncertain', 'expired', 'dead', 'cancelled'
    ));

ALTER TABLE message_delivery_attempts
    DROP CONSTRAINT message_delivery_attempts_outcome_check,
    ADD CONSTRAINT message_delivery_attempts_outcome_check CHECK (
        outcome IN ('accepted', 'failed', 'uncertain')
    );

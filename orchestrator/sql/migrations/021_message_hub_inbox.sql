-- Make held deliveries addressable from channel-specific inbox commands.

ALTER TABLE message_hub_deliveries
    ADD COLUMN recipient_key VARCHAR(500),
    ADD COLUMN acknowledged_at TIMESTAMPTZ;

UPDATE message_hub_deliveries delivery
SET recipient_key = CASE gateway.type
    WHEN 'sms' THEN 'sms:' || COALESCE(NULLIF(delivery.address->>'phone', ''), delivery.id::text)
    WHEN 'telegram' THEN 'telegram:' || COALESCE(
        NULLIF(delivery.address->>'chat_id', ''),
        CASE WHEN delivery.address->>'self' = 'true' THEN 'self' END,
        delivery.id::text
    )
    WHEN 'webhook' THEN 'webhook:' || md5(COALESCE(delivery.address->>'url', delivery.id::text))
    ELSE gateway.key || ':' || delivery.id::text
END
FROM message_gateways gateway
WHERE gateway.id = delivery.gateway_id;

ALTER TABLE message_hub_deliveries
    ALTER COLUMN recipient_key SET NOT NULL,
    DROP CONSTRAINT message_hub_deliveries_status_check,
    ADD CONSTRAINT message_hub_deliveries_status_check CHECK (status IN (
        'pending', 'leased', 'retry_wait', 'accepted', 'held', 'acknowledged',
        'expired', 'dead', 'cancelled'
    ));

CREATE INDEX message_hub_delivery_inbox_idx
    ON message_hub_deliveries (recipient_key, status, created_at)
    WHERE status = 'held';

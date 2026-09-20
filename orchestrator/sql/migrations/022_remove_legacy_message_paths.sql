-- Complete the Message Hub cutover.
--
-- Pending legacy SMS records are retained as held Message Hub deliveries so a
-- deployment cannot turn an old outage backlog into an SMS replay storm.

INSERT INTO message_hub_messages
    (direction, kind, conversation_key, payload, metadata, priority,
     idempotency_key, created_at, expires_at)
SELECT
    'outbound',
    'text',
    legacy.phone_number,
    jsonb_build_object('text', legacy.message),
    jsonb_build_object(
        'source_type', legacy.source_type,
        'source_key', legacy.source_key,
        'source_label', COALESCE(NULLIF(legacy.source_label, ''), legacy.source_type),
        'user_id', legacy.user_id,
        'migrated_from', 'sms_outbox',
        'legacy_id', legacy.id
    ),
    50,
    'legacy-sms-outbox:' || legacy.id,
    legacy.created_at,
    legacy.expires_at
FROM sms_outbox legacy
WHERE legacy.status IN ('pending', 'dispatching')
  AND legacy.expires_at > NOW()
ON CONFLICT (idempotency_key) DO NOTHING;

INSERT INTO message_hub_deliveries
    (message_id, gateway_id, address, payload, recipient_key, status,
     recovery_policy, priority, attempts, max_attempts, available_at,
     last_error, idempotency_key, created_at, updated_at)
SELECT
    message.id,
    gateway.id,
    jsonb_build_object('phone', legacy.phone_number),
    jsonb_build_object('text', legacy.message),
    'sms:' || legacy.phone_number,
    'held',
    'digest_hold',
    50,
    legacy.attempts,
    GREATEST(legacy.attempts + 1, 8),
    NOW(),
    'migrated from legacy SMS outbox; retrieve through inbox',
    'legacy-sms-outbox:' || legacy.id,
    legacy.created_at,
    NOW()
FROM sms_outbox legacy
JOIN message_hub_messages message
  ON message.idempotency_key = 'legacy-sms-outbox:' || legacy.id
JOIN message_gateways gateway ON gateway.key = 'sms-main'
WHERE legacy.status IN ('pending', 'dispatching')
  AND legacy.expires_at > NOW()
ON CONFLICT (idempotency_key) DO NOTHING;

DROP TABLE sms_service_state;
DROP TABLE sms_outbox;

DROP TABLE telegram_relay_rules;
DROP TABLE telegram_relay_destinations;

ALTER TABLE message_relay_endpoints DROP COLUMN legacy_destination_id;
ALTER TABLE message_relay_routes DROP COLUMN legacy_rule_id;

# Message Hub

Message Hub is the single durable path for outbound SMS, Telegram, Messenger,
Reticulum, and webhook deliveries. Producers store a message plus one delivery
per target; background workers claim those deliveries and call the
corresponding gateway.

## Runtime

Migrations `020_message_hub.sql` and `021_message_hub_inbox.sql` create the
queue, gateway health state, incidents, and recipient-scoped held-message
inboxes. Migration `022_remove_legacy_message_paths.sql` completes the cutover:
it preserves unsent SMS records as held Message Hub deliveries and removes the
superseded tables. Migration `023_message_hub_delivery_ack_links.sql` links
queued responses to held inbox items for acknowledgement after delivery.
Migration `024_message_hub_attachments.sql` stores binary media separately
from queue JSON and removes it automatically with its parent message. Migration
`025_message_gateway_dispatch_tokens.sql` adds the stable transport token and
the terminal `uncertain` state used to prevent automatic duplicate sends.

The delivery and gateway-health workers always start with the orchestrator.
The built-in gateways are `sms-main`, `telegram-main`, `messenger-main`,
`reticulum-main`, and `webhook-main`. Their timing, thresholds, retention, and
alert targets use the `MESSAGE_HUB_*` settings in `stack.env.example`.

Telegram-to-SMS routes default to `digest_hold`. Messages accumulated while the
SMS gateway is down remain in the inbox, and recovery creates one summary
instead of replaying the entire backlog.

## Enqueue API

`POST /api/message-hub/messages` requires `X-Service-Key` and returns `202` once
the message and all target deliveries are durably stored.

```json
{
  "direction": "outbound",
  "kind": "text",
  "payload": {"text": "Hello"},
  "priority": 50,
  "ttl_seconds": 900,
  "idempotency_key": "example:42",
  "deliveries": [
    {
      "gateway_key": "sms-main",
      "address": {"phone": "+4712345678"},
      "recovery_policy": "digest_hold",
      "max_attempts": 8
    },
    {
      "gateway_key": "telegram-main",
      "address": {"chat_id": 123456789},
      "recovery_policy": "replay"
    }
  ]
}
```

MMS submissions use `kind: "mms"` and one JPEG, PNG, or GIF attachment:

```json
{
  "direction": "outbound",
  "kind": "mms",
  "payload": {"text": "Weather forecast"},
  "idempotency_key": "weather-image:42",
  "attachments": [{
    "content_type": "image/png",
    "filename": "weather.png",
    "data_base64": "..."
  }],
  "deliveries": [{
    "gateway_key": "sms-main",
    "address": {"phone": "+4712345678"},
    "recovery_policy": "replay"
  }]
}
```

The decoded attachment limit defaults to 5 MB and is configured with
`MESSAGE_HUB_MAX_ATTACHMENT_BYTES`. Message inspection returns attachment
metadata, never the binary content.

Inspection endpoints accept either the service key or an administrator JWT:

- `GET /api/message-hub/gateways`
- `POST /api/message-hub/gateways` (administrator)
- `PATCH /api/message-hub/gateways/<key>/enabled` (administrator)
- `GET /api/message-hub/messages/<id>`
- `GET /api/message-hub/deliveries?status=pending&limit=100`
- `GET /api/message-hub/deliveries/search?statuses=held&query=hello&page=1&page_size=25`
  returns `{items, total, page, page_size}` and also accepts `gateway_key`,
  `recipient`, `source_type`, `source_label`, `created_after`, `created_before`,
  and `sort=asc|desc` filters
- `GET /api/message-hub/delivery-groups/search?statuses=held` returns the same
  pagination envelope with groups keyed by source, conversation, gateway, and recipient
- `GET /api/message-hub/deliveries/<id>` returns delivery and parent-message
  details, attachment metadata, and delivery-attempt history to administrators or services
- `GET /api/message-hub/stats`

Held deliveries can be retrieved without acknowledging them first. The caller
acknowledges returned IDs only after its response is accepted by the gateway:

- `GET /api/message-hub/inbox/summary?recipient_key=sms:%2B4712345678`
- `POST /api/message-hub/inbox/prepare`
- `POST /api/message-hub/inbox/ack`

Queue producers can instead attach `acknowledge_delivery_ids` to a delivery.
Message Hub validates that those held deliveries belong to the same recipient
and acknowledges them atomically when the response delivery is accepted. SMS
command responses use this path so an unsuccessful reply never consumes inbox
items.

Administrator queue actions:

- `POST /api/message-hub/deliveries/<id>/retry`
- `POST /api/message-hub/deliveries/<id>/retry-anyway`
- `POST /api/message-hub/deliveries/<id>/release`
- `POST /api/message-hub/deliveries/<id>/cancel`
- `POST /api/message-hub/deliveries/bulk-action` with up to 500 `delivery_ids`
  and an action of `acknowledge`, `cancel`, `release`, or `retry`
- `POST /api/message-hub/delivery-groups/bulk-action` applies one of those actions
  to an exact group and filter snapshot, processing at most 500 messages per request
- `POST /api/message-hub/deliveries/bulk-filter-action` applies an action to an
  exact delivery-search snapshot in 500-message batches for “select all matching” workflows.
  The UI fixes the snapshot's time bounds before confirmation, excludes later arrivals,
  and reports completed batches if a later request fails.
- `GET /api/message-hub/bulk-operations` returns the administrator audit history.
- `POST /api/message-hub/bulk-operations/<id>/undo` restores unchanged deliveries for
  cancel and mark-read operations during the ten-minute undo window.
- `POST /api/message-hub/bulk-operations/<id>/resume` continues an interrupted filtered
  operation from its original filter and time snapshot.

Bulk operation records retain the administrator username, action, scope, filter snapshot,
counts, and each delivery's prior state. Audit records remain after the undo window expires.

Automatic retries keep the delivery's `dispatch_token`. The SMS gateway stores
that token in a persistent SQLite receipt ledger before it writes to the modem.
An accepted token returns its cached success after HTTP failures or gateway
restarts, without sending again. If sms-hub stops in the small interval between
starting a modem send and recording the result, the token becomes `uncertain`.
Message Hub will not retry it automatically. An administrator can choose
**Retry anyway**, which warns about the duplicate risk and rotates the token.

The sms-hub ledger is mounted at `/data/sms-delivery-ledger.sqlite3` through the
`sms_hub_data` volume. `SMS_DELIVERY_STALE_SECONDS` controls when an abandoned
in-progress receipt becomes uncertain; accepted and definitely failed receipts
are retained according to `SMS_DELIVERY_RECEIPT_RETENTION_DAYS`.

Gateway outage notifications can use other healthy gateways via
`MESSAGE_HUB_ALERT_TARGETS`, a JSON array of `gateway_key` and `address`
objects. Fully terminal messages and closed incidents are retained for 30 days
by default, configurable with `MESSAGE_HUB_RETENTION_DAYS`.

## PostgreSQL integration tests

The queue concurrency and migration tests create and remove an isolated schema
in a real PostgreSQL database:

```sh
MESSAGE_HUB_TEST_DATABASE_URL=postgresql://user:password@localhost:5433/orchestrator \
  ./.venv/bin/python -m unittest tests.test_message_hub_postgres -v
```

Use a non-production database account with schema creation permission.

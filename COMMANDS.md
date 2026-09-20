# Bot Command Reference

## SMS Bot

**Syntax:** `<command> [args] [key=value] [+flag] [-flag]`

### Authentication & Input Rules

- All senders must be registered users (looked up by phone number). Unknown numbers are rejected.
- Non-admin users must have each command explicitly in their `allowed_commands` list.
- The registered sender phone number is the SMS authentication boundary; PINs are not enforced.
- Typos of up to 1 character are auto-corrected (Damerau-Levenshtein distance ≤ 1).
- Unknown input falls back to the AI NLU handler (if configured).

---

### General

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `help` | `?` | Show all available commands | `[command]` — optional name for detailed help | No |
| `menu` | `m` | Compact numbered dumb-phone menu | — | No |
| `today` | `day`, `1` | Calendar, reminders, weather, and solar summary | — | No |
| `cam` | `camera` | Latest camera snapshot by MMS | — | No |
| `status` | `3` | Configured home entities, solar, and service health | — | No |
| `more` / `back` | — | Navigate long responses | — | No |
| `again` / `cancel` | — | Repeat the last command or clear interaction state | — | No |

Numeric defaults are `1 today`, `2 list show`, `3 status`, `4 inbox`, `5 ideas show`, and `6 help`. They can be overridden per user.

---

### Shopping List

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `list show` | `get/shoppinglist` | Display the current shopping list | — | No |
| `list add <item>` | — | Add an item to the shopping list | `<item>` — item name (required) | No |
| `list rm <item>` | — | Remove an item from the shopping list | `<item>` — item name (required) | No |

---

### Reminders

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `rem in <duration> <message>` | `remind`, `t`, `timer` | Create a reminder or fast timer | `<duration>` — e.g. `45m`, `1h`; `<message>` — reminder text; `repeat=daily\|weekly:MON\|interval:30m` | No |
| `rem list [status]` | `reminders` | List reminders | `[status]` — `active` (default), `snoozed`, `dismissed`, `completed` | No |
| `rem snooze <id> [duration]` | `snooze` | Snooze a reminder | `<id>` — reminder ID; `[duration]` — default `10m` | No |
| `rem dismiss <id>` | `dismiss` | Permanently dismiss a reminder | `<id>` — reminder ID (required) | No |

**Examples:**
```
rem in 45m check oven
rem in 1h take pills repeat=daily
rem in 2h meeting repeat=weekly:MON
rem list snoozed
rem snooze 7 30m
rem dismiss 7
```

---

### Energy & Solar

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `chart` | `chart/today`, `solar` | Today's combined solar production (Growatt + EcoFlow) | — | No |

---

### Home Automation

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `home/dev <entity_id>` | `trigger/tv` | Trigger a Home Assistant automation or entity | `<entity_id>` — HA entity ID (required) | No |
| `scene <name> [argument]` | `mode` | Run an allowlisted named scene; configured automations can receive a duration argument | `<name>` or `list` | No |
| `run <name>` | `job` | Start an allowlisted orchestrator job | `<name>` or `list` | No |

**Example:**
```
home/dev switch.living_room_lights
scene bed
scene heat 60
```

---

### Telegram Conversations

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `tg/list` | `tg/convos` | List recent Telegram conversations (numbered index) | — | No |
| `tg/send <num> <message>` | — | Send a message to conversation `#<num>`; sets sticky reply context | `<num>` — 1-based index from `tg/list` or raw `chat_id`; `<message>` — text | No |
| `tg/reply <message>` | `tg/r`, `r`, `reply` | Reply to the last active Telegram conversation | `<message>` — text to send | No |
| `tg/use <num\|chat_id>` | `tg/target` | Select the sticky conversation used by replies and unaddressed MMS photos | `<num>` — index from `tg/list`, or a raw chat ID | No |

**Note:** `tg/reply` requires a prior `tg/send`, `tg/use`, or an incoming relayed message to establish context. The context is persisted across relay restarts.

After `tg/use`, an MMS containing a JPEG, PNG, or GIF is forwarded to the selected conversation. Its text part becomes the Telegram caption. An MMS may also select its target directly with a caption such as `tg/send 2 Snow at the cabin`.

**Examples:**
```
tg/list
tg/send 2 Hey, are you home?
tg/reply On my way
tg/use 2
```

---

### Message Routes

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `relay` | `relay/list`, `relay/ls` | List message routes and their targets | — | No |
| `relay on [route]` | `relay/start`, `relay/enable` | Enable a route; the route may be omitted when exactly one SMS route exists | route key, index, or name | No |
| `relay off [route]` | `relay/stop`, `relay/disable` | Disable a route; the route may be omitted when exactly one SMS route exists | route key, index, or name | No |

**Examples:**
```
relay
relay on
relay off telegram-to-lora
```

---

### AI Assistant

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `ai <message>` | `chat` | Chat with the AI assistant, or describe what you want to do | `<message>` — free-text prompt | No* |

Keeps the last 5 turns of context per session. NLU-dispatched commands still use the sender's normal command permissions.

**Examples:**
```
ai what's on my shopping list?
ai remind me to call mum in 2 hours
chat turn off the living room lights
```

---

### Dumb-phone Utilities

| Command | Description |
|---|---|
| `agenda [days]` / `cal` | Upcoming calendar events |
| `note <text>` | Add to the ideas note |
| `ideas show` | Retrieve the ideas note |
| `print today\|weather\|list` | Print useful views on the thermal printer |
| `print note <text>` | Print an arbitrary note |
| `news [count]` | Retrieve RSS headlines from `news_feed_url` |
| `bus <destination>` | Call the configured transit webhook |
| `brief <HHMM\|off>` | Schedule or disable a durable daily SMS brief |
| `quiet <HHMM> <HHMM>` | Queue proactive messages during quiet hours |
| `checkin <minutes>` | Begin a safety deadline; reply `OK` to acknowledge |

Long command results are kept within one GSM-7 SMS when their characters permit it. Reply `more`, `back`, or `again` instead of retyping the command.

---

## Message Router — Telegram Connector

The Telegram connector is a **passive message source**, not a command bot. Route control is exposed through the orchestrator UI and the SMS `relay` commands.

### Overview

- Authenticates with Telegram via TDLib using a real phone-number account (not a bot token).
- Listens for incoming messages and evaluates every enabled route for the configured Telegram source endpoint.
- Supports message types: `messageText`, `messagePhoto`, `messageDocument`. All other types are discarded before the rule engine runs.
- Outgoing messages are ignored entirely.
- Configuration (endpoints + many-source/many-target routes) is hot-reloaded at runtime from the orchestrator.
- Every matching route and every enabled target is dispatched; routes do not use first-match-wins behavior.

---

### Advanced Route Filter Schema

Normal configuration is managed through **Message Routes** in the orchestrator UI. The condition format below is available as an optional per-route filter.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | required | Route label used in the UI and logs |
| `key` | `string` | required | Stable lowercase key used by commands and APIs |
| `enabled` | `bool` | `true` | Master switch for the route |
| `filter` | `dict` | `null` | Condition tree. `null` or empty forwards every message from the selected sources |
| `sources` | `list` | required* | Source endpoints; `match_all_sources` can be used instead |
| `targets` | `list` | required | Independently switchable target endpoints |

---

### Message Fields (available in conditions)

All condition `field` values reference the normalized message object:

| Field | Type | Description |
|---|---|---|
| `message_id` | `int` | TDLib message ID |
| `chat_id` | `int` | Positive = private DM, negative = group/channel |
| `chat_title` | `string \| null` | Chat display name; may be `null` early in a session |
| `chat_type` | `string` | `"private"` (chat_id > 0), `"group"` (chat_id ≤ 0), or `"unknown"` |
| `sender_id` | `int \| null` | User ID; `null` for channel/anonymous senders |
| `sender_name` | `string \| null` | Display name; currently always `null` (not resolved) |
| `text` | `string \| null` | Message body for `messageText`; `null` for media |
| `media_type` | `string \| null` | `null`, `"photo"`, or `"document"` |
| `caption` | `string \| null` | Caption on photo/document messages |
| `timestamp` | `int` | Unix epoch timestamp (`message.date` from TDLib) |

---

### Condition Operators

A leaf condition node has three keys: `field`, `op`, and `value`.

| Operator | Behaviour | `value` type |
|---|---|---|
| `eq` | `field == value` — exact equality | scalar |
| `neq` | `field != value` | scalar |
| `in` | `field` is a member of `value` | list |
| `not_in` | `field` is not a member of `value` | list |
| `contains` | `value` is a substring of `field` | string |
| `regex` | `re.search(value, field)` — partial match, not anchored | string (regex) |
| `exists` | `field is not None`; `value` is ignored | any / omit |
| `gt` | `field > value`; safe — returns `false` if field is `null` | number |
| `lt` | `field < value`; safe — returns `false` if field is `null` | number |

**Regex notes:** use `(?i)` flag for case-insensitive matching. Unknown operators log an error and evaluate to `false`.

---

### Logical Combinators

Combinators nest arbitrarily — a combinator node can contain leaf nodes or other combinator nodes.

| Combinator | Value type | Behaviour |
|---|---|---|
| `all` | list of condition nodes | AND — all children must be `true`. Short-circuits on first `false`. |
| `any` | list of condition nodes | OR — at least one child must be `true`. Short-circuits on first `true`. |
| `not` | single condition node (not a list) | NOT — inverts the child result. |

---

### Actions

The action representation below is the connector's compiled runtime format. The Message Routes UI generates it from route targets; normal route setup does not require editing actions directly.

#### `forward`

Forwards the message to a configured destination.

| Field | Default | Description |
|---|---|---|
| `type` | required | `"forward"` |
| `destination` | required | The `id` of a configured destination |
| `redact` | `[]` | List of redaction rules applied to message fields before sending (see below) |
| `include_fields` | `null` | Whitelist of payload fields to include. Takes precedence over `exclude_fields`. |
| `exclude_fields` | `null` | Blacklist of payload fields to omit. Ignored if `include_fields` is set. |

**Redaction rule** (each entry in `redact`):

| Sub-field | Description |
|---|---|
| `field` | The message field to apply the pattern to (e.g. `text`) |
| `pattern` | Python regex pattern to search for |
| `replace` | Replacement string. Defaults to `"[REDACTED]"` |

> **Note:** For `sms` destinations, `chat_title` and `sender_name` are always injected into the payload regardless of field filters.

#### `skip`

Silently drops the message. No parameters other than `type`.

| Field | Description |
|---|---|
| `type` | `"skip"` |

#### `log`

Emits a structured log line with `chat_id`, `chat_type`, `chat_title`, `sender_id`, `sender_name`, `message_id`, and content type.

| Field | Default | Description |
|---|---|---|
| `type` | required | `"log"` |
| `level` | `"info"` | Log level: `debug`, `info`, `warning`, or `error` |

---

### Destinations

#### `webhook`

HTTP POST to any URL with the message payload as JSON.

| Field | Default | Description |
|---|---|---|
| `id` | required | Unique identifier referenced by `forward` actions |
| `type` | required | `"webhook"` |
| `url` | `""` | Full HTTP(S) URL to POST to |
| `headers` | `{}` | Extra request headers (e.g. `Authorization: Bearer …`) |
| `timeout` | `10.0` | Request timeout in seconds |
| `retry.max_attempts` | `3` | Total attempts (first try + retries) |
| `retry.backoff_seconds` | `2.0` | Base delay; actual delay = `backoff_seconds × 2^(attempt - 1)` (exponential backoff) |

Payload: the normalized message as a JSON object after redaction and field filtering.

#### `sms`

Forwards the message to a phone number via the SMS bot.

| Field | Default | Description |
|---|---|---|
| `id` | required | Unique identifier referenced by `forward` actions |
| `type` | required | `"sms"` |
| `config.phone` | `""` | E.164 recipient phone number (e.g. `+46701234567`) |

- Submits text to `POST {ORCHESTRATOR_API_URL}/api/message-hub/messages`; the orchestrator queues it durably and its SMS gateway consumer delivers it.
- Message format: `"{chat_title} | {sender_name}: {text}"` (degrades gracefully if either is absent).
- Stored messages retain the Telegram `chat_id` and title so they can be filtered by source with the SMS `inbox` command.
- `inbox` reads recipient-scoped held deliveries and acknowledges them only after a successful SMS response.
- Binary Telegram media is not queued; captions and media placeholders are retained as text.

---

### Internal HTTP API

These endpoints are consumed by the SMS bot's `tg/*` commands and internal services — not by end users directly. All endpoints require an `X-Service-Key` header.

| Endpoint | Method | Description |
|---|---|---|
| `/internal/reload` | `POST` | Hot-reload destinations and rules from the orchestrator |
| `/internal/auth/code` | `POST` | Submit a Telegram login auth code or password during login flow |
| `/api/telegram/conversations` | `GET` | Return the list of recent conversations (used by `tg/list`) |
| `/api/telegram/send` | `POST` | Send a message to a chat by `chat_id` (used by `tg/send` / `tg/reply`) |
| `/api/telegram/send-media` | `POST` | Send a multipart image upload and optional caption to a chat |
| `/api/telegram/send-self` | `POST` | Send an operational alert to the relay account's Saved Messages |
| `/api/telegram/context/<phone>` | `GET` | Get the sticky reply context (last `chat_id`) for a phone number |
| `/api/telegram/context` | `POST` | Set the sticky reply context for a phone number |

The orchestrator exposes the routing control plane under `/api/telegram_relay`:

| Endpoint | Method | Description |
|---|---|---|
| `/endpoints` | `GET`, `POST` | List or save source/target endpoints |
| `/endpoints/<id>` | `DELETE` | Delete an endpoint and remove it from routes |
| `/routes` | `GET`, `POST` | List or save many-source/many-target routes |
| `/routes/<key>/enabled` | `PATCH` | Toggle a complete route |
| `/routes/preset/enabled` | `PATCH` | Toggle every preset route |
| `/routes/<route>/targets/<endpoint>/enabled` | `PATCH` | Toggle one target without affecting the others |
| `/routes/<id>` | `DELETE` | Delete a route |

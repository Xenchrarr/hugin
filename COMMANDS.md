# Bot Command Reference

## SMS Bot

**Syntax:** `<command> [args] [key=value] [+flag] [-flag] [#PIN]`

### Authentication & Input Rules

- All senders must be registered users (looked up by phone number). Unknown numbers are rejected.
- Non-admin users must have each command explicitly in their `allowed_commands` list.
- Commands marked **[PIN]** require a `#<4–8 digit PIN>` appended to the message.
- Typos of up to 1 character are auto-corrected (Damerau-Levenshtein distance ≤ 1).
- Unknown input falls back to the AI NLU handler (if configured).

---

### General

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `help` | `?` | Show all available commands | `[command]` — optional name for detailed help | No |

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
| `rem in <duration> <message>` | `remind` | Create a reminder | `<duration>` — e.g. `45m`, `1h`; `<message>` — reminder text; `repeat=daily\|weekly:MON\|interval:30m` | No |
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
| `home/dev <entity_id>` | `trigger/tv` | Trigger a Home Assistant automation or entity | `<entity_id>` — HA entity ID (required) | **Yes** |

**Example:**
```
home/dev switch.living_room_lights #1234
```

---

### Telegram Conversations

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `tg/list` | `tg/convos` | List recent Telegram conversations (numbered index) | — | No |
| `tg/send <num> <message>` | — | Send a message to conversation `#<num>`; sets sticky reply context | `<num>` — 1-based index from `tg/list` or raw `chat_id`; `<message>` — text | **Yes** |
| `tg/reply <message>` | `tg/r` | Reply to the last active Telegram conversation | `<message>` — text to send | **Yes** |

**Note:** `tg/reply` requires a prior `tg/send` or an incoming relayed message to establish context.

**Examples:**
```
tg/list
tg/send 2 Hey, are you home? #1234
tg/reply On my way #1234
```

---

### Relay Rules

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `relay/list` | `relay/ls` | List all Telegram relay rules with `[ON]`/`[OFF]` status and priority | — | No |
| `relay/start <num\|name>` | `relay/enable` | Enable a relay rule | `<num\|name>` — 1-based index from `relay/list` or exact/prefix rule name | **Yes** |
| `relay/stop <num\|name>` | `relay/disable` | Disable a relay rule | `<num\|name>` — 1-based index from `relay/list` or exact/prefix rule name | **Yes** |

**Examples:**
```
relay/list
relay/start 1 #1234
relay/stop urgent-alerts #1234
```

---

### AI Assistant

| Command | Aliases | Description | Parameters | PIN |
|---|---|---|---|---|
| `ai <message>` | `chat` | Chat with the AI assistant, or describe what you want to do | `<message>` — free-text prompt | No* |

**\*** NLU-dispatched commands inherit their own PIN requirements. Keeps last 5 turns of context per session.

**Examples:**
```
ai what's on my shopping list?
ai remind me to call mum in 2 hours
chat turn off the living room lights
```

---

## Telegram Relay Bot

The Telegram Relay bot is a **passive message-forwarding service**, not a command bot. It has no user-facing commands.

### Overview

- Authenticates with Telegram via TDLib using a real phone-number account (not a bot token).
- Listens for all incoming messages and applies a rule engine to route them.
- Supports message types: `messageText`, `messagePhoto`, `messageDocument`. All other types are discarded before the rule engine runs.
- Outgoing messages are ignored entirely.
- Configuration (rules + destinations) is hot-reloaded at runtime from the orchestrator.

---

### Rule Schema

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | required | Label used in log output |
| `priority` | `int` | `100` | Rules are sorted ascending — **lower number = higher priority** |
| `enabled` | `bool` | `true` | Disabled rules are filtered out at startup |
| `conditions` | `dict` | `null` | Condition tree. `null` or empty = catch-all (always matches) |
| `actions` | `list` | `[]` | Ordered list of actions to execute when the rule matches |
| `continue` / `continue_on_match` | `bool` | `false` | If `true`, keep evaluating lower-priority rules after a match. If `false` (default), stop at first match |

> **Note:** In YAML config the field is `continue`; when sourced from the orchestrator API it is `continue_on_match`.

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

- Calls `POST {SMS_BOT_URL}/api/sms/send`. `SMS_BOT_URL` defaults to `http://sms-hub:5050`.
- Message format: `"{chat_title} | {sender_name}: {text}"` (degrades gracefully if either is absent).
- Timeout: 15 s. No retry logic.

---

### Full Config Example

```yaml
destinations:
  - id: main_webhook
    type: webhook
    url: "https://hooks.example.com/relay"
    headers:
      Authorization: "Bearer secret"
    timeout: 10.0
    retry:
      max_attempts: 3
      backoff_seconds: 2.0

  - id: my_sms
    type: sms
    config:
      phone: "+46701234567"

rules:
  - name: "Audit log — runs before all others, always continues"
    priority: 5
    continue: true
    conditions:
      all:
        - field: chat_id
          op: in
          value: [-1001234567890, -1009876543210]
    actions:
      - type: log
        level: info

  - name: "Critical alerts from ops group"
    priority: 10
    conditions:
      all:
        - field: chat_id
          op: in
          value: [-1001234567890]
        - field: text
          op: regex
          value: "(?i)(alert|critical|error|down)"
    actions:
      - type: forward
        destination: main_webhook
        redact:
          - field: text
            pattern: "\\+?[0-9]{8,15}"
            replace: "[PHONE]"

  - name: "Forward photos from any group"
    priority: 50
    conditions:
      all:
        - field: chat_type
          op: eq
          value: "group"
        - field: media_type
          op: eq
          value: "photo"
    actions:
      - type: forward
        destination: my_sms
        include_fields: [chat_title, sender_name, caption]

  - name: "default-skip"
    priority: 999
    actions:
      - type: skip
```

---

### Internal HTTP API

These endpoints are consumed by the SMS bot's `tg/*` commands and internal services — not by end users directly. All endpoints require an `X-Service-Key` header.

| Endpoint | Method | Description |
|---|---|---|
| `/internal/reload` | `POST` | Hot-reload destinations and rules from the orchestrator |
| `/internal/auth/code` | `POST` | Submit a Telegram login auth code or password during login flow |
| `/api/telegram/conversations` | `GET` | Return the list of recent conversations (used by `tg/list`) |
| `/api/telegram/send` | `POST` | Send a message to a chat by `chat_id` (used by `tg/send` / `tg/reply`) |
| `/api/telegram/context/<phone>` | `GET` | Get the sticky reply context (last `chat_id`) for a phone number |
| `/api/telegram/context` | `POST` | Set the sticky reply context for a phone number |

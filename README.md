# Homelab Stack

A Docker Compose stack for home automation, energy monitoring, and task orchestration.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  orchestrator-   │     │   hugin-core      │     │  ecoflow-monitor │
│  frontend  :80   │     │   :5100           │     │                  │
└────────┬────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                       │                         │
         ▼                       │                         │
┌─────────────────┐              │              ┌──────────▼─────────┐
│  orchestrator    │◄────────────┘              │ energy-postgres    │
│                  │──┐                         │ :5432              │
└────────┬────────┘  │                          └────────────────────┘
         │           │
         ▼           ▼
┌────────────────┐ ┌──────────────────┐
│ orchestrator-  │ │ powershell-runner │
│ postgres :5433 │ └──────────────────┘
└────────────────┘

┌─────────────────┐  ┌──────────────┐  ┌────────────────────┐
│ overlia-power-  │  │   sms-hub    │  │ telegram-relay     │
│ bot             │  │              │  │ :8080              │
└─────────────────┘  └──────────────┘  └────────────────────┘

┌──────────────┐  ┌──────────────┐
│ file-server  │  │              │
│ (internal)   │  │              │
└──────────────┘  └──────────────┘
```

## Services

### Databases

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **energy-postgres** | `postgres:16-alpine` | 5432 | Stores power/energy data for hugin-core and ecoflow-monitor |
| **orchestrator-postgres** | `postgres:17` | 5433 | Stores job definitions, schedules, and run history |

### Core

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **hugin-core** | `xenchrarr/hugin-core` | 5100 | Central API aggregating power consumption (Growatt), weather (Yr), energy prices (Tibber), Home Assistant data, camera feeds, and shopping lists (Simplenote) |
| **ecoflow-monitor** | `xenchrarr/ecoflow-monitor` | — | Monitors EcoFlow power stations via MQTT, storing metrics to Postgres |

### Bots

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **overlia-power-bot** | `xenchrarr/overlia-power-bot` | — | Telegram bot for power/energy notifications |
| **sms-hub** | `xenchrarr/sms-hub` | — | SMS command handler via SIM800 USB modem; triggers Home Assistant automations and fetches shopping lists |

### Orchestrator

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **orchestrator** | `xenchrarr/orchestrator` | — | Job scheduler and execution engine for automated tasks (PowerShell scripts, git syncs, power aggregation) |
| **orchestrator-frontend** | `xenchrarr/orchestrator-frontend` | 80 | Angular web UI for managing scheduled jobs |
| **powershell-runner** | `xenchrarr/powershell-runner` | — | Executes PowerShell scripts on behalf of the orchestrator |
| **telegram-relay** | `xenchrarr/telegram-relay` | 8080 | Telegram connector for the endpoint-and-route message router |
| **file-server** | `nginx:alpine` | — | Serves shared log files from orchestrator job runs (internal only) |

### SMS resilience

Outbound Telegram and reminder SMS messages pass through a durable PostgreSQL
outbox in the orchestrator. The orchestrator monitors modem readiness, alerts the
Telegram Relay account's Saved Messages after a confirmed outage, and retains
messages for retrieval with the SMS `inbox` commands. Missed reminders are sent
as a compact digest after recovery; other messages remain grouped by source to
avoid a recovery-time message burst.

Text and image replies produced by SMS and MMS commands also enter the durable
queue before the modem sends them. Binary media is stored separately from queue
JSON and removed by the normal retention cleanup. Incoming modem messages are
removed only after the reply is stored, and `inbox` items are acknowledged only
when that queued reply is accepted by the SMS gateway.

The SMS hub preserves stored modem messages across restarts. Registered senders
can select a Telegram conversation with `tg/use <num>` and forward an MMS image
to that conversation; JPEG, PNG, and GIF payloads are supported.

## Setup

### 1. Configure environment

```bash
cp stack.env.example stack.env
# Edit stack.env with your credentials
```

Key variables to set:

- **Database** — `ENERGY_DB_PASSWORD`, `JOB_DB_USER_NAME`, `JOB_DB_PASSWORD`
- **EcoFlow** — `ECOFLOW_ACCESS_KEY`, `ECOFLOW_SECRET_KEY`
- **Hugin Core** — `TIBBER_ACCESS_TOKEN`, `HA_URL`, `HA_TOKEN`, `SIMPLENOTE_EMAIL`, `SIMPLENOTE_PASSWORD`, `SERVICE_KEY`
- **Telegram bot** — `TELEGRAM_API_KEY`, `ALLOWED_USER_IDS`
- **Telegram connector** — `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE_NUMBER`, `DB_ENCRYPTION_KEY`; optionally `MESSAGE_RELAY_ENDPOINT_KEY`
- **SMS** — register the sender's phone number on an orchestrator user
- **Orchestrator** — `TEAMS_WEBHOOK_URL`, `GIT_USERNAME`, `GIT_PASSWORD`, `GIT_REPO_URLS`

### 2. Build and push images

```bash
# Build all images
make build

# Push all to Docker Hub
make push

# Build/push a single service
make build-hugin-core
make push-hugin-core
```

### 3. Deploy

```bash
docker compose up -d
```

## Hardware Requirements

- **SIM800/Quectel USB modem** mapped via a `by-id` symlink (e.g. `/dev/serial/by-id/usb-Quectel_...`) to `/dev/ttyUSB0` inside the `sms-hub` container — update the `devices` entry in `docker-compose.yml` to match your modem's path

## Volumes

| Volume | Purpose |
|--------|---------|
| `energy_pgdata` | Power monitoring database |
| `orchestrator_pgdata` | Orchestrator database |
| `shared_logs` | Job execution logs (shared between orchestrator and file-server) |
| `powershell_scripts` | PowerShell scripts managed by the runner |
| `telegram_tdlib` | TDLib session data for telegram-relay |

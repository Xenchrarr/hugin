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
│                  │──┐                         │ :5433              │
└────────┬────────┘  │                          └────────────────────┘
         │           │
         ▼           ▼
┌────────────────┐ ┌──────────────────┐
│ orchestrator-  │ │ powershell-runner │
│ postgres :5432 │ └──────────────────┘
└────────────────┘

┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
│ overlia-power-  │  │   sms-hub    │  │ file-server   │
│ bot             │  │              │  │ :8001         │
└─────────────────┘  └──────────────┘  └───────────────┘
```

## Services

### Databases

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **energy-postgres** | `postgres:16-alpine` | 5433 | Stores power/energy data for hugin-core and ecoflow-monitor |
| **orchestrator-postgres** | `postgres:17` | 5432 | Stores job definitions, schedules, and run history |

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
| **file-server** | `nginx:alpine` | 8001 | Serves shared log files from orchestrator job runs |

## Setup

### 1. Configure environment

```bash
cp stack.env.example stack.env
# Edit stack.env with your credentials
```

Key variables to set:

- **Database** — `ENERGY_DB_PASSWORD`, `JOB_DB_USER_NAME`, `JOB_DB_PASSWORD`
- **EcoFlow** — `ECOFLOW_ACCESS_KEY`, `ECOFLOW_SECRET_KEY`
- **Growatt** — `GROWATT_USERNAME`, `GROWATT_PASSWORD`
- **Tibber** — `TIBBER_ACCESS_TOKEN`
- **Home Assistant** — `HA_URL`, `HA_TOKEN`
- **Telegram** — `TELEGRAM_API_KEY`
- **SMS** — `ALLOWED_SENDERS`, `SENDER_PINS`

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

- **SIM800 USB modem** mounted at `/dev/ttyUSB_SIM800` (for the sms-hub service)

## Volumes

| Volume | Purpose |
|--------|---------|
| `energy_pgdata` | Power monitoring database |
| `orchestrator_pgdata` | Orchestrator database |
| `shared_logs` | Job execution logs (shared between orchestrator and file-server) |
| `powershell_scripts` | PowerShell scripts managed by the runner |

# Hugin orchestrator

## Workflows

Automation is code-defined under `src/workflows`. A module-level function decorated
with `@step` declares its JSON input/output contract. Compose registered steps with
`workflow(...)`; modules named `steps.py` and `definitions.py` are discovered at
startup. Every run stores the workflow version and full definition snapshot, and
each step has durable status, input, output, errors, logs, heartbeat, and artifacts.

The built-in Hugin capabilities are version 1 workflows with typed inputs. Optional
development or extension jobs receive a generic one-step adapter. Schedules should
be recreated by selecting a deployed workflow from `/api/jobs/types`; old job rows
are deliberately not translated and migration 031 disables them. Supported triggers are `daily`, `weekly`,
`interval`, and durable `once_at`.

Use `CallbackExecution` for remote work completed through a callback. It registers
the step correlation before starting the action and maps the remote result into a
workflow outcome. `IncidentActionExecution` provides a durable, leased idempotency
ledger for side effects in retryable monitor response workflows.

Key endpoints:

- `GET /api/workflows/list`
- `GET /api/workflows/<key>`
- `POST /api/workflows/<key>/execute` with `{ "input": {} }`
- `GET /api/workflows/runs/<run-id>`
- `GET /api/joblog/getforjob?job_run_id=...&step_run_id=...&after_id=...`

## Monitors

Monitors are code-defined under `src/monitors/definitions`. They combine a registered
source, evaluator, interval, and response workflow. Runtime state, checkpoints,
observations, deduplicated incidents, poll leases, and response dispatch leases are
stored in PostgreSQL. `core.http_health`, `core.each_observation`, and
`core.all_signals_by_correlation`, and `core.ordered_checks_by_correlation` are included as generic primitives;
product-specific Snog integrations are intentionally excluded.

Key endpoints:

- `GET /api/monitors/list`
- `GET /api/monitors/<key>`
- `POST /api/monitors/<key>/run`
- `PUT /api/monitors/<key>/enabled`
- `POST /api/monitors/incidents/<incident-id>/retry`

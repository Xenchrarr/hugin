# Hugin orchestrator

## Workflows

Workflow steps are code-defined under `src/workflows`. A module-level function
decorated with `@step(key, version=...)` declares a versioned JSON input/output
contract and owns the side-effecting implementation. Workflow composition is data:
administrators build drafts in the GUI, connect compatible workflow inputs and
earlier step outputs, validate them, and publish immutable revisions stored in
PostgreSQL. Every run stores the full compiled definition snapshot; every step run
also stores its exact code-step version, durable status, resolved input, output,
errors, logs, heartbeat, and artifacts.

Both step schemas must be object schemas with an explicit `properties` map and
`additionalProperties` policy. The GUI exposes those named properties as connection
ports. A step accepting or returning arbitrary JSON should put it under a named
property with an unconstrained `{}` child schema (for example `core.echo.value`),
rather than declaring an anonymous top-level object that the GUI cannot address.

Branches are represented as structured `when` conditions on ordered steps. This is
deliberately a guarded sequential plan rather than a general graph: it is simple to
resume and audit while still supporting “if X run A, if Y run B.” Later steps can
join mutually exclusive paths with a typed `first_available` binding. Conditions
support `eq`, `ne`, `exists`, `is_true`, `is_false`, `all`, `any`, and `not` in the
runtime; the first GUI slice exposes the common single-condition form.

Draft writes use optimistic locking. Publishing assigns the next workflow version,
and a database trigger prevents a published revision from being changed or deleted.
Schedules and monitor incidents pin a revision UUID, so later publication cannot
change already configured automation. Old job rows are deliberately not translated;
migration 031 disables them for recreation. Supported triggers are `daily`,
`weekly`, `interval`, manual `once`, and durable `once_at`.

Use `CallbackExecution` for remote work completed through a callback. It registers
the step correlation before starting the action and maps the remote result into a
workflow outcome. `IncidentActionExecution` provides a durable, leased idempotency
ledger for side effects in retryable monitor response workflows.

Key endpoints:

- `GET /api/workflows/list`
- `GET /api/workflows/manage`
- `GET /api/workflows/steps`
- `POST /api/workflows/`
- `GET|PUT|DELETE /api/workflows/<key>/draft`
- `POST /api/workflows/<key>/validate`
- `POST /api/workflows/<key>/publish`
- `GET /api/workflows/<key>/revisions`
- `POST /api/workflows/<key>/revisions/<version>/clone`
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

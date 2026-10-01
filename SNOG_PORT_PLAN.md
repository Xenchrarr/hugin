# Snog-to-Hugin convergence plan

The repositories do not share usable Git ancestry, so this is a semantic port:
Hugin keeps its own messaging, calendar, reminder, alarm, Reticulum, printing,
energy, SMS, and phone services while adopting Snog's reusable orchestration
architecture. Legacy scheduled-job input is intentionally not supported.

## Implemented foundation

- Code-defined, versioned workflow and step registries with discovery, inferred
  bindings, conditions, failure policy, schema validation, definition snapshots,
  cancellation, heartbeat, output limits, artifacts, and aggregate outcomes.
- Durable workflow step runs, step-correlated logs, cursor log reads, run files,
  run activity, configurable worker pools, maximum concurrency, and durable
  one-time schedules.
- Native typed workflows for every production Hugin job capability. Optional
  development extensions retain a generic adapter. Migration 031 disables old
  schedules so operators can recreate them against the new contracts.
- Generic direct and callback execution policies. PowerShell execution now uses
  an accept-and-callback protocol with job/step correlation, service-key
  authentication, batched logging, retry, and final-log flushing.
- Durable monitor runtime with checkpoints, poll and dispatch leases,
  observations, correlation evaluators, deduplicated incidents, response runs,
  retries, and an idempotent incident-action ledger.
- Administrator APIs and frontend views for workflow catalog/detail/execution,
  typed recursive input forms with Advanced JSON, step logs/artifacts,
  monitor health/incidents/toggles/retries, and schedule concurrency/`once_at`.

## Deliberate boundaries

- Snog's LifeX, DR, Portal, log-reader/archive, AVI, control-room, and tenant
  implementations are product-specific and are not copied into Hugin. Their
  extension points are present: add Hugin monitor sources, monitor definitions,
  workflows, and incident actions without changing the runtime.
- Workflow execution remains linear. Parallel branches, automatic step retry,
  and recovery of an already-running external action remain future runtime work.
- Existing job run history is preserved. Existing schedules are disabled, not
  translated or deleted.

## Deployment sequence

1. Back up the orchestrator PostgreSQL database and deploy orchestrator,
   frontend, and PowerShell runner together.
2. Set a non-empty shared `SERVICE_KEY` and review the worker, heartbeat,
   one-time grace, monitor lease, and log batching values in `stack.env`.
3. Start the orchestrator once so migrations 031 and 032 apply; verify the
   workflow catalog and that legacy schedules are disabled.
4. Recreate schedules through Jobs using the typed workflow forms. Exercise
   each external integration manually before enabling its schedule.
5. Add Hugin-specific monitor definitions only after their response workflows
   are deployed; enable them from the monitor UI after a manual poll succeeds.

## Release gates

- Apply both migrations to a staging PostgreSQL copy and inspect constraints,
  indexes, disabled schedules, and preserved run history.
- Run the backend suite and production Angular build.
- Execute one synchronous native workflow, one PowerShell callback workflow,
  one cancelled workflow, one `once_at` schedule, and one monitor incident retry.
- Verify cursor log polling, step correlation, artifact links, scheduler restart,
  stale-run handling, and duplicate monitor polling from two replicas.

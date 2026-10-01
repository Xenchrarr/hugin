from __future__ import annotations

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

from src.monitors import MonitorPollContext, monitor_evaluator_registry, monitor_registry, monitor_source_registry
from src.persistence.MonitorStorage import MonitorStorage
from src.persistence.JobStorage import JobStorage
from src.persistence.WorkflowStepRunStorage import WorkflowStepRunStorage
from src.services.workflows.workflow_service import create_workflow_run, submit_workflow_run

log = logging.getLogger(__name__)


class MonitorRunner:
    def __init__(self, owner=None):
        self.owner = owner or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"

    def poll(self, key: str) -> dict:
        definition = monitor_registry.get(key)
        if definition is None: raise ValueError(f"Monitor not found: {key}")
        with MonitorStorage() as storage:
            storage.ensure_monitor(definition)
            lease_seconds = max(
                definition.interval_seconds,
                int(os.getenv("MONITOR_POLL_LEASE_SECONDS", "300")),
            )
            if not storage.try_acquire_poll_lease(key, self.owner, lease_seconds):
                return {"monitor_key": key, "skipped": True}
            try:
                now=datetime.now(timezone.utc); source=monitor_source_registry.get(definition.source)
                evaluator=monitor_evaluator_registry.get(definition.evaluator)
                result=source.poll(MonitorPollContext(key,now,storage.get_checkpoint(key)),definition.source_config)
                inserted=storage.insert_observations(key,result.observations)
                observations=storage.get_observations_since(key,now-timedelta(seconds=definition.observation_window_seconds))
                candidates=evaluator.evaluate(observations,definition.evaluator_config)
                claimed=[item for item in (storage.claim_incident(definition,c) for c in candidates) if item]
                margin=max(0,int(definition.source_config.get('observation_cleanup_margin_seconds',300)))
                storage.delete_observations_before(
                    key, now-timedelta(seconds=definition.observation_window_seconds+margin))
                storage.finish_poll(key,self.owner,result.checkpoint,result.errors)
                return {"monitor_key":key,"observations_received":len(result.observations),
                        "observations_inserted":inserted,"candidates_found":len(candidates),
                        "incidents_claimed":claimed,"source_errors":list(result.errors),"skipped":False}
            except Exception as exc:
                storage.finish_poll(key,self.owner,storage.get_checkpoint(key),(str(exc),))
                raise


class MonitorDispatcher:
    def __init__(self): self.owner=f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"
    def dispatch_pending(self, limit=20):
        count=0
        with MonitorStorage() as storage:
            storage.reconcile_finished_responses()
            for _ in range(limit):
                row=storage.claim_pending_incident(self.owner,int(os.getenv('MONITOR_DISPATCH_LEASE_SECONDS','300')))
                if not row: break
                incident_id,workflow_key,run_id,workflow_input=row
                try:
                    run=JobStorage().get_job_run_by_id(run_id)
                    if run is None:
                        create_workflow_run(workflow_key,workflow_input,run_by='monitor',run_by_group='system',job_run_id=run_id)
                        run=JobStorage().get_job_run_by_id(run_id)
                    storage.register_incident_run(incident_id,run_id)
                    if run.status != 'Started':
                        storage.mark_dispatched(incident_id,run.status,run.result if run.status=='Error' else '')
                        continue
                    if WorkflowStepRunStorage().get_step_runs(run_id):
                        storage.mark_dispatched(incident_id,'Running')
                        continue
                    future=submit_workflow_run(run_id)
                    storage.mark_dispatched(incident_id,'Running')
                    future.add_done_callback(lambda completed,i=incident_id:self._complete(i,completed))
                    count+=1
                except Exception as exc:
                    storage.mark_dispatched(incident_id,'Pending',str(exc));log.exception('Monitor dispatch failed')
        return count

    @staticmethod
    def _complete(incident_id,future):
        with MonitorStorage() as storage:
            error=future.exception()
            storage.reconcile_finished_responses()
            if error: storage.mark_dispatched(incident_id,'Error',str(error))

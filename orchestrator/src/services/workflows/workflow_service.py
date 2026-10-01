from __future__ import annotations

import datetime
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from src.models.orchestrator.Job import Job
from src.models.orchestrator.JobRun import JobRun
from src.persistence.JobStorage import JobStorage
from src.persistence.WorkflowStepRunStorage import WorkflowStepRunStorage
from src.services.workflows.workflow_definition_service import validate_value_against_schema
from src.services.workflows.workflow_executor import WorkflowExecutor
from src.workflows.definitions import discover_workflows, workflow_registry
from src.workflows.hugin import definitions as _hugin_definitions  # noqa: F401

discover_workflows()

_workers = ThreadPoolExecutor(
    max_workers=max(1, int(os.environ.get("WORKFLOW_WORKER_THREADS", "4"))),
    thread_name_prefix="workflow",
)


def get_workflows():
    return workflow_registry.list()


def get_workflow(key: str):
    return workflow_registry.get(key)


def workflow_input_for_job(job: Job) -> dict:
    if job.workflow_input:
        return job.workflow_input
    if not job.param:
        return {}
    # Legacy jobs are represented as workflows with a single string parameter.
    workflow = get_workflow(job.job_type)
    properties = workflow.input_schema.get("properties", {}) if workflow else {}
    if properties.get("param", {}).get("type") == "string":
        return {"param": job.param}
    try:
        value = json.loads(job.param)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Workflow param must contain a JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("Workflow param must contain a JSON object")
    return value


def create_workflow_run(workflow_key: str, workflow_input: dict, *, run_by: str,
                        run_by_group: str = "system", job: Job | None = None,
                        job_run_id: uuid.UUID | str | None = None,
                        metadata: dict | None = None) -> uuid.UUID:
    item = get_workflow(workflow_key)
    if item is None:
        raise ValueError(f"Workflow not found: {workflow_key}")
    validate_value_against_schema(workflow_input, item.input_schema, "workflow.input")
    run = JobRun(
        id=str(job_run_id) if job_run_id else "",
        name=job.name if job else item.key,
        start_time=datetime.datetime.now(datetime.timezone.utc),
        end_time=None,
        status="Started",
        job_type=item.key,
        result="",
        job_id=job.id if job else None,
        parameter="",
        run_by=run_by,
        run_by_group=run_by_group,
        metadata=metadata or {},
        workflow_version=item.version,
        workflow_input=workflow_input,
        workflow_definition=item.definition(),
    )
    return JobStorage().create_job_run(run)


def submit_workflow_run(job_run_id: uuid.UUID | str):
    return _workers.submit(WorkflowExecutor().execute_run, str(job_run_id))


def start_workflow(workflow_key: str, workflow_input: dict, *, run_by: str,
                   run_by_group: str = "admin") -> uuid.UUID:
    run_id = create_workflow_run(workflow_key, workflow_input, run_by=run_by,
                                 run_by_group=run_by_group)
    submit_workflow_run(run_id)
    return run_id


def run_workflow_job(job: Job, job_run_id: uuid.UUID | str | None = None) -> uuid.UUID:
    if job_run_id is None:
        job_run_id = create_workflow_run(job.job_type, workflow_input_for_job(job),
                                         run_by="system", run_by_group="system", job=job)
    WorkflowExecutor().execute_run(str(job_run_id))
    return uuid.UUID(str(job_run_id))


def get_workflow_run(job_run_id: str) -> dict | None:
    run = JobStorage().get_job_run_by_id(job_run_id)
    if run is None or run.workflow_version is None:
        return None
    return {
        "run": run.to_dict(include_workflow_definition=True),
        "steps": [item.to_dict() for item in WorkflowStepRunStorage().get_step_runs(job_run_id)],
        "artifacts": JobStorage().get_job_run_files(job_run_id),
    }

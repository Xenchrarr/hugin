from __future__ import annotations

import datetime
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

from src.models.orchestrator.Job import Job
from src.models.orchestrator.JobRun import JobRun
from src.persistence.JobStorage import JobStorage
from src.persistence.WorkflowStepRunStorage import WorkflowStepRunStorage
from src.persistence.WorkflowDefinitionStorage import WorkflowDefinitionStorage
from src.services.workflows.workflow_compiler import WorkflowCompiler
from src.services.workflows.workflow_definition_service import validate_value_against_schema
from src.services.workflows.workflow_executor import WorkflowExecutor
from src.workflows.core import steps as _core_steps  # noqa: F401
from src.workflows.hugin import steps as _hugin_steps  # noqa: F401
from src.workflows.powershell import steps as _powershell_steps  # noqa: F401

_WORKFLOW_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,119}$")

_workers = ThreadPoolExecutor(
    max_workers=max(1, int(os.environ.get("WORKFLOW_WORKER_THREADS", "4"))),
    thread_name_prefix="workflow",
)


def get_workflows():
    return WorkflowDefinitionStorage().list_published()


def get_all_workflow_revisions():
    return WorkflowDefinitionStorage().list_all_published()


def get_workflow_catalog():
    return WorkflowDefinitionStorage().list_catalog()


def get_workflow(key: str, version: int | None = None):
    return WorkflowDefinitionStorage().get_published(key, version)


def get_workflow_revision(revision_id: str):
    return WorkflowDefinitionStorage().get_revision(revision_id)


def get_workflow_draft(key: str, user: str, *, create: bool = True):
    storage = WorkflowDefinitionStorage()
    return storage.ensure_draft(key, user) if create else storage.get_draft(key)


def get_workflow_revisions(key: str):
    return WorkflowDefinitionStorage().list_revisions(key)


def clone_workflow_revision(key: str, version: int, lock_version: int, user: str):
    if version < 1:
        raise ValueError("Workflow revision version must be positive")
    return WorkflowDefinitionStorage().clone_revision(key, version, lock_version, user)


def create_workflow(key: str, name: str, description: str, user: str):
    if not isinstance(key, str) or not _WORKFLOW_KEY.fullmatch(key):
        raise ValueError("Workflow key must start with a letter and contain only lowercase letters, numbers, dots, dashes, or underscores")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Workflow name is required")
    editor = {
        "key": key,
        "description": description or "",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "steps": [],
    }
    return WorkflowDefinitionStorage().create(key, name.strip(), description or "", editor, user)


def save_workflow_draft(key: str, editor: dict, name: str, description: str,
                        lock_version: int, user: str):
    if not isinstance(editor, dict) or editor.get("key") != key:
        raise ValueError("Draft key does not match the workflow")
    return WorkflowDefinitionStorage().save_draft(
        key, editor, name, description, lock_version, user)


def validate_workflow_draft(editor: dict) -> dict:
    return WorkflowCompiler().compile(editor, version=1)


def publish_workflow(key: str, name: str, description: str, editor: dict,
                     lock_version: int, user: str):
    if not isinstance(editor, dict) or editor.get("key") != key:
        raise ValueError("Draft key does not match the workflow")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Workflow name is required")
    compiled = WorkflowCompiler().compile(editor, version=1)
    return WorkflowDefinitionStorage().publish(
        key, name.strip(), description or "", editor, compiled, lock_version, user)


def delete_workflow_draft(key: str, lock_version: int, user: str) -> None:
    WorkflowDefinitionStorage().delete_draft(key, lock_version, user)


def archive_workflow(key: str, user: str) -> None:
    WorkflowDefinitionStorage().archive(key, user)


def workflow_input_for_job(job: Job) -> dict:
    return job.workflow_input or {}


def create_workflow_run(workflow_key: str, workflow_input: dict, *, run_by: str,
                        run_by_group: str = "system", job: Job | None = None,
                        workflow_revision_id: uuid.UUID | str | None = None,
                        job_run_id: uuid.UUID | str | None = None,
                        metadata: dict | None = None) -> uuid.UUID:
    pinned_revision_id = (job.workflow_revision_id if job is not None else None) or workflow_revision_id
    item = get_workflow_revision(pinned_revision_id) if pinned_revision_id else get_workflow(workflow_key)
    if item is None:
        raise ValueError(f"Workflow not found: {workflow_key}")
    if item.key != workflow_key:
        raise ValueError("Pinned workflow revision does not match its workflow key")
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

from __future__ import annotations

import uuid
from flask import Blueprint, g, request

from src.auth import require_admin, require_auth
from src.services.workflows.workflow_definition_service import WorkflowDefinitionError
from src.services.workflows.workflow_service import (
    get_workflow, get_workflow_run, get_workflows, start_workflow,
)
from src.workflows.registry import workflow_step_registry

workflow_blueprint = Blueprint("workflows", __name__)


@workflow_blueprint.route("/steps", methods=["GET"])
@require_admin
def list_steps():
    return [item.to_dict() for item in workflow_step_registry.list()]


@workflow_blueprint.route("/", methods=["GET"])
@workflow_blueprint.route("/list", methods=["GET"])
@require_admin
def list_workflows():
    return [item.to_dict() for item in get_workflows()]


@workflow_blueprint.route("/<workflow_key>", methods=["GET"])
@require_admin
def workflow_detail(workflow_key: str):
    item = get_workflow(workflow_key)
    return (item.to_dict(), 200) if item else ({"message": "Workflow not found"}, 404)


@workflow_blueprint.route("/<workflow_key>/execute", methods=["POST"])
@require_admin
def execute_workflow(workflow_key: str):
    data = request.get_json(silent=True) or {}
    workflow_input = data.get("input", {})
    if not isinstance(workflow_input, dict):
        return {"message": "input must be an object"}, 400
    try:
        payload = getattr(g, "jwt_payload", {})
        run_id = start_workflow(workflow_key, workflow_input,
                                run_by=str(payload.get("sub", payload.get("user_id", "admin"))),
                                run_by_group="admin")
        return {"message": "Workflow started", "job_run_id": str(run_id)}, 202
    except (ValueError, WorkflowDefinitionError) as exc:
        return {"message": str(exc)}, 400


@workflow_blueprint.route("/runs/<job_run_id>", methods=["GET"])
@require_auth
def workflow_run(job_run_id: str):
    try:
        uuid.UUID(job_run_id)
    except ValueError:
        return {"message": "Invalid job_run_id"}, 400
    result = get_workflow_run(job_run_id)
    return (result, 200) if result else ({"message": "Workflow run not found"}, 404)

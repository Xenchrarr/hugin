from __future__ import annotations

import uuid
from flask import Blueprint, g, request

from src.auth import require_admin, require_auth
from src.persistence.WorkflowDefinitionStorage import WorkflowConflictError
from src.services.workflows.workflow_compiler import WorkflowCompileError
from src.services.workflows.workflow_definition_service import WorkflowDefinitionError
from src.services.workflows.workflow_service import (
    archive_workflow, clone_workflow_revision, create_workflow, delete_workflow_draft,
    get_workflow, get_workflow_catalog, get_workflow_draft, get_workflow_revisions,
    get_workflow_run, get_workflows, publish_workflow, save_workflow_draft,
    start_workflow, validate_workflow_draft,
)
from src.workflows.registry import workflow_step_registry

workflow_blueprint = Blueprint("workflows", __name__)


def _user() -> str:
    payload = getattr(g, "jwt_payload", {})
    return str(payload.get("sub", payload.get("user_id", "admin")))


def _body() -> dict:
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("Request body must be an object")
    return value


def _error(exc: Exception):
    if isinstance(exc, WorkflowCompileError):
        return exc.to_dict(), 400
    if isinstance(exc, WorkflowConflictError):
        return {"message": str(exc)}, 409
    return {"message": str(exc)}, 400


@workflow_blueprint.route("/steps", methods=["GET"])
@require_admin
def list_steps():
    return [item.to_dict() for item in workflow_step_registry.list()]


@workflow_blueprint.route("/", methods=["GET"])
@workflow_blueprint.route("/list", methods=["GET"])
@require_admin
def list_workflows():
    return [item.to_dict() for item in get_workflows()]


@workflow_blueprint.route("/manage", methods=["GET"])
@require_admin
def workflow_catalog():
    return get_workflow_catalog()


@workflow_blueprint.route("/", methods=["POST"])
@require_admin
def create_definition():
    try:
        data = _body()
        item = create_workflow(data.get("key"), data.get("name"), data.get("description", ""), _user())
        return item.to_dict(include_editor=True), 201
    except (ValueError, WorkflowDefinitionError) as exc:
        return _error(exc)


@workflow_blueprint.route("/<workflow_key>/draft", methods=["GET"])
@require_admin
def workflow_draft(workflow_key: str):
    item = get_workflow_draft(workflow_key, _user())
    return (item.to_dict(include_editor=True), 200) if item else ({"message": "Workflow not found"}, 404)


@workflow_blueprint.route("/<workflow_key>/draft", methods=["PUT"])
@require_admin
def update_workflow_draft(workflow_key: str):
    try:
        data = _body()
        item = save_workflow_draft(
            workflow_key, data.get("editor_definition"), data.get("name", workflow_key),
            data.get("description", ""), int(data.get("lock_version", 0)), _user())
        return item.to_dict(include_editor=True)
    except (TypeError, ValueError, WorkflowDefinitionError) as exc:
        return _error(exc)


@workflow_blueprint.route("/<workflow_key>/validate", methods=["POST"])
@require_admin
def validate_definition(workflow_key: str):
    try:
        data = _body()
        editor = data.get("editor_definition")
        if not isinstance(editor, dict) or editor.get("key") != workflow_key:
            raise ValueError("Draft key does not match the workflow")
        return {"valid": True, "compiled_definition": validate_workflow_draft(editor)}
    except (ValueError, WorkflowDefinitionError) as exc:
        return _error(exc)


@workflow_blueprint.route("/<workflow_key>/publish", methods=["POST"])
@require_admin
def publish_definition(workflow_key: str):
    try:
        data = _body()
        item = publish_workflow(
            workflow_key, data.get("name", workflow_key), data.get("description", ""),
            data.get("editor_definition"), int(data.get("lock_version", 0)), _user())
        return item.to_dict(include_editor=True)
    except (TypeError, ValueError, WorkflowDefinitionError) as exc:
        return _error(exc)


@workflow_blueprint.route("/<workflow_key>/revisions", methods=["GET"])
@require_admin
def workflow_revisions(workflow_key: str):
    return [item.to_dict() for item in get_workflow_revisions(workflow_key)]


@workflow_blueprint.route("/<workflow_key>/revisions/<int:version>/clone", methods=["POST"])
@require_admin
def clone_revision(workflow_key: str, version: int):
    try:
        data = _body()
        item = clone_workflow_revision(
            workflow_key, version, int(data.get("lock_version", 0)), _user())
        return item.to_dict(include_editor=True), 201
    except (TypeError, ValueError) as exc:
        return _error(exc)


@workflow_blueprint.route("/<workflow_key>/draft", methods=["DELETE"])
@require_admin
def remove_workflow_draft(workflow_key: str):
    try:
        lock_version = int(request.args.get("lock_version", "0"))
        delete_workflow_draft(workflow_key, lock_version, _user())
        return "", 204
    except (TypeError, ValueError) as exc:
        return _error(exc)


@workflow_blueprint.route("/<workflow_key>/archive", methods=["POST"])
@require_admin
def archive_definition(workflow_key: str):
    try:
        archive_workflow(workflow_key, _user())
        return {"message": "Workflow archived"}
    except ValueError as exc:
        return _error(exc)


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
        run_id = start_workflow(workflow_key, workflow_input,
                                run_by=_user(),
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

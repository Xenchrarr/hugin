from __future__ import annotations

import json
import os
import threading
import traceback
from dataclasses import dataclass, field

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.models.orchestrator.JobRunFile import JobRunFile
from src.persistence.DatabaseLogger import DatabaseLogger
from src.persistence.JobDb import JobDb
from src.persistence.JobStorage import JobStorage
from src.persistence.WorkflowStepRunStorage import WorkflowStepRunStorage
from src.services.core.cancellation_service import cleanup, is_cancelled, register_cancellation_token
from src.services.core.threading_service import JobCancelledException
from src.services.workflows.workflow_definition_service import (
    resolve_step_input, should_run_step, validate_value_against_schema,
    validate_workflow_definition,
)
from src.workflows.contracts import OnFailure, StepArtifact, StepContext, StepResult
from src.workflows.registry import workflow_step_registry

_MAX_OUTPUT = 256 * 1024
_DONE = {"Finished", "Partial", "Nothing", "Skipped"}
_ACTIVE = {"Pending", "Started"}
_OUTCOME_STATUS = {"succeeded": "Finished", "partial": "Partial", "nothing": "Nothing"}


class WorkflowExecutionError(RuntimeError):
    pass


@dataclass
class _Progress:
    context: dict
    outcomes: list[str] = field(default_factory=list)
    failures: int = 0
    skipped: int = 0

    def record(self, key: str, status: str, output: dict) -> None:
        self.context["steps"][key] = {"status": status, "output": output}
        if status == "Skipped":
            self.skipped += 1
        elif status in _DONE:
            self.outcomes.append({"Finished": "succeeded", "Partial": "partial",
                                  "Nothing": "nothing"}[status])


class _Heartbeat:
    def __init__(self, storage, step_id: str, run_id: str):
        self.storage, self.step_id, self.run_id = storage, step_id, run_id
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name=f"workflow-heartbeat-{step_id[:8]}")

    def _run(self):
        interval = max(1, int(os.environ.get("WORKFLOW_HEARTBEAT_SECONDS", "30")))
        while not self.stop.wait(interval):
            try:
                self.storage.heartbeat(self.step_id, self.run_id)
            finally:
                JobDb.instance().close_connection()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.stop.set()
        self.thread.join(timeout=2)


class WorkflowExecutor:
    def __init__(self, workflow_storage=None, job_storage=None, logger=None):
        self.steps = workflow_storage or WorkflowStepRunStorage()
        self.jobs = job_storage or JobStorage()
        self.logger = logger or DatabaseLogger()

    @staticmethod
    def _result(value) -> StepResult:
        result = StepResult() if value is None else StepResult(output=value) if isinstance(value, dict) else value
        if not isinstance(result, StepResult) or not isinstance(result.output, dict):
            raise WorkflowExecutionError("Workflow steps must return StepResult, dict, or None")
        if result.outcome not in _OUTCOME_STATUS:
            raise WorkflowExecutionError(f"Invalid step outcome: {result.outcome}")
        if len(json.dumps(result.output).encode()) > _MAX_OUTPUT:
            raise WorkflowExecutionError("Workflow step output exceeds 256 KiB")
        if any(not isinstance(item, StepArtifact) for item in result.artifacts):
            raise WorkflowExecutionError("Invalid workflow artifact")
        return result

    def _finish_parent(self, run, status: str, result: str):
        run.status, run.result = status, result
        self.jobs.update_job_run(run)

    def _log(self, level, message, run_id, step_id, trace=""):
        # Observability is best-effort: a logging outage must not change the
        # result of the action being observed.
        try:
            method = {"ERROR": self.logger.log_error, "WARNING": self.logger.log_warning}.get(
                level, self.logger.log_info)
            if level == "ERROR":
                method(message, trace, run_id, step_id)
            else:
                method(message, run_id, step_id)
        except Exception as exc:
            print(f"Could not persist workflow-step lifecycle log: {exc}")

    def _execute_step(self, run, invocation, resolved, attempt):
        registered = workflow_step_registry.get(invocation["step"])
        step_run = self.steps.create_step_run(run.id, invocation["key"], invocation["step"],
                                              resolved, attempt)
        self.steps.mark_step_started(step_run.id)
        local = ThreadLocalSingleton.instance().thread_local
        local.step_run_id = str(step_run.id)
        self._log("INFO", f"Step '{invocation['key']}' started (attempt {attempt})",
                  str(run.id), str(step_run.id))
        try:
            context = StepContext(str(run.id), str(step_run.id), invocation["key"], attempt, run.run_by)
            with _Heartbeat(self.steps, str(step_run.id), str(run.id)):
                result = self._result(registered.execute(context, resolved))
            validate_value_against_schema(result.output, registered.spec.output_schema,
                                          f"steps.{invocation['key']}.output")
            for artifact in result.artifacts:
                self.jobs.create_job_run_file(JobRunFile(
                    job_run_id=str(run.id), step_run_id=str(step_run.id),
                    original_filename=artifact.original_filename,
                    storage_path=artifact.storage_path, download_url=artifact.download_url))
            status = _OUTCOME_STATUS[result.outcome]
            self.steps.finish_step_run(step_run.id, status, result.output, {}, result.summary)
            self._log("INFO", f"Step '{invocation['key']}' finished with {status}",
                      str(run.id), str(step_run.id))
            return status, result.output
        except JobCancelledException:
            self.steps.finish_step_run(step_run.id, "Cancelled", {}, {"message": "Cancelled"}, "Cancelled")
            raise
        except Exception as exc:
            self.steps.finish_step_run(step_run.id, "Error", {},
                                       {"type": type(exc).__name__, "message": str(exc)}, str(exc))
            self._log("ERROR", f"Step '{invocation['key']}' failed: {exc}",
                      str(run.id), str(step_run.id), traceback.format_exc())
            raise
        finally:
            local.step_run_id = None

    def execute_run(self, job_run_id: str) -> None:
        job_run_id = str(job_run_id)
        local = ThreadLocalSingleton.instance().thread_local
        local.job_run_id = job_run_id
        local.step_run_id = None
        register_cancellation_token(job_run_id)
        run = None
        try:
            run = self.jobs.get_job_run_by_id(job_run_id)
            if run is None:
                raise WorkflowExecutionError(f"Workflow run not found: {job_run_id}")
            if run.status != "Started":
                return
            if run.workflow_version is None or not run.workflow_definition:
                raise WorkflowExecutionError(f"Job run is not a workflow execution: {job_run_id}")
            definition = validate_workflow_definition(run.workflow_definition, workflow_step_registry)
            if definition.get("key") != run.job_type or definition.get("version") != run.workflow_version:
                raise WorkflowExecutionError("Workflow snapshot does not match run identity")

            previous = {}
            for item in self.steps.get_step_runs(run.id):
                if item.step_key not in previous or item.attempt > previous[item.step_key].attempt:
                    previous[item.step_key] = item
            progress = _Progress({"input": run.workflow_input or {}, "steps": {}})
            for invocation in definition["steps"]:
                old = previous.get(invocation["key"])
                if old and old.status in _DONE:
                    progress.record(old.step_key, old.status, old.output)
                    continue
                if old and old.status in _ACTIVE:
                    raise WorkflowExecutionError(
                        f"Step '{invocation['key']}' already has an active attempt")
                if is_cancelled(job_run_id):
                    raise JobCancelledException("Workflow execution was cancelled")
                attempt = old.attempt + 1 if old else 1
                if not should_run_step(invocation, progress.context["input"]):
                    item = self.steps.create_step_run(run.id, invocation["key"], invocation["step"], {}, attempt)
                    self.steps.finish_step_run(item.id, "Skipped", {}, {}, "Condition was false")
                    progress.record(invocation["key"], "Skipped", {})
                    continue
                registered = workflow_step_registry.get(invocation["step"])
                try:
                    resolved = resolve_step_input(invocation.get("inputs", {}), progress.context)
                    validate_value_against_schema(resolved, registered.spec.input_schema,
                                                  f"steps.{invocation['key']}.input")
                except Exception as exc:
                    item = self.steps.create_step_run(
                        run.id, invocation["key"], invocation["step"], {}, attempt)
                    self.steps.mark_step_started(item.id)
                    self.steps.finish_step_run(
                        item.id, "Error", {},
                        {"type": type(exc).__name__, "message": str(exc)}, str(exc))
                    self._log("ERROR", f"Step '{invocation['key']}' input failed: {exc}",
                              job_run_id, str(item.id), traceback.format_exc())
                    progress.context["steps"][invocation["key"]] = {"status": "Error", "output": {}}
                    if OnFailure(invocation["on_failure"]) is OnFailure.CONTINUE:
                        progress.failures += 1
                        continue
                    self._finish_parent(run, "Error", f"Workflow stopped preparing '{invocation['key']}': {exc}")
                    return
                try:
                    status, output = self._execute_step(run, invocation, resolved, attempt)
                    progress.record(invocation["key"], status, output)
                except JobCancelledException:
                    raise
                except Exception as exc:
                    progress.context["steps"][invocation["key"]] = {"status": "Error", "output": {}}
                    if OnFailure(invocation["on_failure"]) is OnFailure.CONTINUE:
                        progress.failures += 1
                        continue
                    self._finish_parent(run, "Error", f"Workflow stopped at '{invocation['key']}': {exc}")
                    return
            if progress.failures:
                if "succeeded" in progress.outcomes or "partial" in progress.outcomes:
                    self._finish_parent(run, "Partial", "Workflow finished with partial success")
                else:
                    self._finish_parent(run, "Error", "All executed workflow steps failed or did nothing")
            elif "partial" in progress.outcomes:
                self._finish_parent(run, "Partial", "Workflow finished with partial success")
            elif not progress.outcomes or all(item == "nothing" for item in progress.outcomes):
                self._finish_parent(run, "Nothing", "Workflow had nothing to do")
            else:
                self._finish_parent(run, "Finished", "Workflow finished")
        except JobCancelledException:
            if run is not None:
                self._finish_parent(run, "Cancelled", "Workflow was cancelled")
        except Exception as exc:
            if run is not None and run.status == "Started":
                self._finish_parent(run, "Error", f"Workflow failed: {exc}")
            raise
        finally:
            cleanup(job_run_id)
            local.job_run_id = None
            local.step_run_id = None
            JobDb.instance().close_connection()

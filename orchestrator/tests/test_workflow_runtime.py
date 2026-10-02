import sys
import threading
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

src_package = types.ModuleType("src")
src_package.__path__ = [str(Path(__file__).resolve().parents[1] / "src")]
sys.modules.setdefault("src", src_package)

from src.monitors import (
    Observation, all_signals_by_correlation, each_observation,
    ordered_checks_by_correlation,
)
from src.monitors.actions import IncidentActionExecution
from src.services.core.callback_registry import CallbackRegistry
from src.services.workflows.workflow_definition_service import (
    WorkflowDefinitionError, evaluate_condition, resolve_step_input,
    validate_workflow_definition,
    validate_value_against_schema,
)
from src.services.workflows.workflow_compiler import WorkflowCompileError, WorkflowCompiler
from src.workflows import CallbackExecution, StepContext, StepResult, workflow
from src.workflows.definitions import WorkflowRegistry
from src.workflows.registry import StepRegistry
from src.workflows.step import RegisteredStep, StepSpec


def _producer(_context, values):
    return StepResult(output={"value": values["seed"] + 1})


def _consumer(_context, values):
    return values


class WorkflowRuntimeTests(unittest.TestCase):
    def test_deployed_step_contracts_are_gui_addressable(self):
        from src.workflows.core import steps as core_steps
        from src.workflows.hugin import steps as _hugin_steps  # noqa: F401
        from src.workflows.powershell import steps as _powershell_steps  # noqa: F401
        from src.workflows.registry import workflow_step_registry

        for registered in workflow_step_registry.list():
            with self.subTest(step=registered.spec.key):
                for schema in (registered.spec.input_schema, registered.spec.output_schema):
                    self.assertEqual("object", schema.get("type"))
                    self.assertIsInstance(schema.get("properties"), dict)
                    self.assertIn("additionalProperties", schema)
                    self.assertLessEqual(set(schema.get("required", [])), set(schema["properties"]))

        echoed = core_steps.echo_step.execute(
            StepContext("run", "step", "echo", 1), {"value": {"answer": 42}})
        self.assertEqual({"value": {"answer": 42}}, echoed.output)

        with self.assertRaisesRegex(ValueError, "properties map"):
            StepRegistry().register(RegisteredStep(
                StepSpec("test.anonymous", input_schema={"type": "object"}), _consumer))

    def test_step_registry_keeps_deployed_versions(self):
        steps = StepRegistry()
        first = steps.register(RegisteredStep(StepSpec("test.versioned", version=1), _consumer))
        second = steps.register(RegisteredStep(StepSpec("test.versioned", version=2), _consumer))
        self.assertIs(first, steps.get("test.versioned", 1))
        self.assertIs(second, steps.get("test.versioned", 2))
        self.assertIs(second, steps.get("test.versioned"))

    def test_compiles_branch_conditions_and_first_available_merge(self):
        steps = StepRegistry()
        steps.register(RegisteredStep(StepSpec(
            "test.producer", input_schema={"type": "object", "required": ["seed"],
                "properties": {"seed": {"type": "integer"}}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"value": {"type": "integer"}},
                           "additionalProperties": False}), _producer))
        steps.register(RegisteredStep(StepSpec(
            "test.consumer", input_schema={"type": "object", "required": ["value"],
                "properties": {"value": {"type": "integer"}},
                "additionalProperties": False}), _consumer))
        definition = WorkflowCompiler(steps).compile({
            "key": "test.branch", "input_schema": {"type": "object", "required": ["seed", "route"],
                "properties": {"seed": {"type": "integer"}, "route": {"type": "string"}}},
            "steps": [
                {"key": "path_a", "step": "test.producer", "bindings": {
                    "seed": {"source": "workflow_input", "path": ["seed"]}},
                 "when": {"op": "eq", "left": {"source": "workflow_input", "path": ["route"]},
                          "right": {"source": "literal", "value": "a"}}},
                {"key": "path_b", "step": "test.producer", "bindings": {
                    "seed": {"source": "workflow_input", "path": ["seed"]}},
                 "when": {"op": "eq", "left": {"source": "workflow_input", "path": ["route"]},
                          "right": {"source": "literal", "value": "b"}}},
                {"key": "merge", "step": "test.consumer", "bindings": {"value": {
                    "source": "first_available", "candidates": [
                        {"source": "step_output", "step_key": "path_a", "path": ["value"], "optional": True},
                        {"source": "step_output", "step_key": "path_b", "path": ["value"], "optional": True},
                    ]}}},
            ],
        }, version=1)
        self.assertEqual(1, definition["steps"][0]["step_version"])
        self.assertEqual({"$first_available": [
            {"$ref": "$.steps.path_a.output.value", "$optional": True},
            {"$ref": "$.steps.path_b.output.value", "$optional": True},
        ]}, definition["steps"][2]["inputs"]["value"])
        self.assertTrue(evaluate_condition(definition["steps"][0]["when"], {
            "input": {"route": "a"}, "steps": {}}))
        self.assertEqual({"value": 7}, resolve_step_input(
            definition["steps"][2]["inputs"], {"input": {}, "steps": {
                "path_a": {"status": "Skipped", "output": {}},
                "path_b": {"status": "Finished", "output": {"value": 7}},
            }}))

    def test_legacy_run_if_is_rejected(self):
        steps = StepRegistry()
        steps.register(RegisteredStep(StepSpec("test.consumer"), _consumer))
        with self.assertRaises(WorkflowDefinitionError):
            validate_workflow_definition({"key": "test.legacy", "version": 1,
                "input_schema": {"type": "object"}, "steps": [{"key": "consumer",
                    "step": "test.consumer", "inputs": {},
                    "run_if": {"input": "enabled", "equals": True}}]}, steps)

    def test_compiler_rejects_incompatible_binding(self):
        steps = StepRegistry()
        steps.register(RegisteredStep(StepSpec(
            "test.consumer", input_schema={"type": "object", "required": ["value"],
                "properties": {"value": {"type": "integer"}},
                "additionalProperties": False}), _consumer))
        with self.assertRaises(WorkflowCompileError):
            WorkflowCompiler(steps).compile({
                "key": "test.bad", "input_schema": {"type": "object", "properties": {
                    "name": {"type": "string"}}}, "steps": [{"key": "consume",
                    "step": "test.consumer", "bindings": {"value": {
                        "source": "workflow_input", "path": ["name"]}}}]}, version=1)

    def test_infers_workflow_and_previous_step_bindings(self):
        steps = StepRegistry()
        workflows = WorkflowRegistry(steps)

        producer = steps.register(RegisteredStep(StepSpec(
            "test.producer", input_schema={"type": "object", "required": ["seed"],
                "properties": {"seed": {"type": "integer"}}, "additionalProperties": False},
            output_schema={"type": "object", "required": ["value"],
                "properties": {"value": {"type": "integer"}},
                "additionalProperties": False}), _producer))
        consumer = steps.register(RegisteredStep(StepSpec(
            "test.consumer", input_schema={"type": "object", "required": ["value"],
                "properties": {"value": {"type": "integer"}},
                "additionalProperties": False}), _consumer))

        definition = workflow("test.inference", producer, consumer, version=1,
                              registry=workflows).definition()
        self.assertEqual({"$ref": "$.input.seed"}, definition["steps"][0]["inputs"]["seed"])
        self.assertEqual({"$ref": "$.steps.producer.output.value"},
                         definition["steps"][1]["inputs"]["value"])
        self.assertEqual(["seed"], definition["input_schema"]["required"])

    def test_schema_and_optional_reference_validation(self):
        validate_value_against_schema({"count": 2}, {
            "type": "object", "required": ["count"],
            "properties": {"count": {"type": "integer", "minimum": 1}},
        })
        with self.assertRaises(WorkflowDefinitionError):
            validate_value_against_schema({"count": 0}, {
                "type": "object", "properties": {"count": {"type": "integer", "minimum": 1}},
            })
        self.assertEqual({}, resolve_step_input(
            {"missing": {"$ref": "$.input.missing", "$optional": True}},
            {"input": {}, "steps": {}},
        ))

    def test_callback_registry_correlates_and_deduplicates(self):
        registry = CallbackRegistry()
        registry.register("step:1")
        threading.Thread(target=lambda: registry.signal(
            "step:1", "Finished", {"ok": True}, "done")).start()
        self.assertEqual(("Finished", {"ok": True}, "done"), registry.wait("step:1", 1))
        self.assertTrue(registry.signal("step:1", "Error", {}, "late retry"))
        registry.cleanup("step:1")

    def test_callback_execution_translates_remote_status(self):
        registry = CallbackRegistry()
        context = StepContext("run-1", "step-1", "remote", 1)

        def start(_context, _inputs):
            registry.signal("step:step-1", "PartialSuccess", {"changed": 2}, "two changed")

        result = CallbackExecution(registry, 1, "Remote work").execute(start, context, {})
        self.assertEqual("partial", result.outcome)
        self.assertEqual({"changed": 2}, result.output)

    def test_incident_action_execution_uses_durable_action_key(self):
        calls = []

        class Store:
            def execute_once(self, incident_id, action_key, handler):
                calls.append((incident_id, action_key))
                return handler()

        result = IncidentActionExecution(lambda: Store()).execute(
            lambda _context, _inputs: StepResult(output={"ticket": "OPS-1"}),
            StepContext("run-1", "step-1", "create-ticket", 1),
            {"incident_id": "incident-1"},
        )
        self.assertEqual([("incident-1", "create-ticket")], calls)
        self.assertEqual({"ticket": "OPS-1"}, result.output)

    def test_monitor_evaluator_deduplicates_by_correlation_key(self):
        now = datetime.now(timezone.utc)
        observation = Observation("event-1", now, frozenset({"down"}), "service-a")
        candidate = each_observation([observation], {"signal": "down"})[0]
        self.assertEqual("service-a", candidate.dedupe_key)
        self.assertEqual("down", candidate.incident_type)

    def test_monitor_correlates_distinct_signals_inside_window(self):
        now = datetime.now(timezone.utc)
        observations = [
            Observation("event-1", now, frozenset({"request"}), "chain-a"),
            Observation("event-2", now, frozenset({"failure"}), "chain-a"),
        ]
        incidents = all_signals_by_correlation(observations, {
            "required_signals": ["request", "failure"],
            "within_seconds": 60,
        })
        self.assertEqual(1, len(incidents))
        self.assertEqual("chain-a", incidents[0].dedupe_key)
        self.assertEqual(2, len(incidents[0].evidence))

    def test_hugin_catalog_uses_typed_native_workflows(self):
        from src.workflows.hugin import definitions as _hugin_definitions  # noqa: F401
        from src.workflows.powershell import definitions as _powershell_definitions  # noqa: F401
        from src.workflows.definitions import workflow_registry

        phone = workflow_registry.get("phone_call")
        script = workflow_registry.get("run_script")
        news = workflow_registry.get("print_news")
        self.assertEqual(["target"], phone.input_schema["required"])
        self.assertEqual(["script_name"], script.input_schema["required"])
        self.assertEqual("integer", news.input_schema["properties"]["count"]["type"])

    def test_monitor_matches_ordered_scoped_events(self):
        now = datetime.now(timezone.utc)
        observations = [
            Observation("2", now, frozenset({"timeout.failed"}), "request-1"),
            Observation("1", now, frozenset({"timeout.started"}), "request-1"),
        ]
        incidents = ordered_checks_by_correlation(observations, {
            "within_seconds": 120,
            "checks": [{"key": "timeout", "required_signals": ["started", "failed"],
                        "within_seconds": 60}],
        })
        self.assertEqual("timeout:request-1", incidents[0].dedupe_key)
        self.assertEqual(["1", "2"], [item.source_event_id for item in incidents[0].evidence])


if __name__ == "__main__":
    unittest.main()

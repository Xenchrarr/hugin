from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from src.services.workflows.workflow_definition_service import (
    WorkflowDefinitionError,
    validate_value_against_schema,
    validate_workflow_definition,
)
from src.workflows.registry import StepRegistry, workflow_step_registry

_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,119}$")
_STEP_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class WorkflowIssue:
    code: str
    path: list[str | int]
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "path": self.path, "message": self.message}


class WorkflowCompileError(WorkflowDefinitionError):
    def __init__(self, issues: list[WorkflowIssue]):
        self.issues = issues
        super().__init__(issues[0].message if issues else "Workflow definition is invalid")

    def to_dict(self) -> dict:
        return {"message": str(self), "issues": [item.to_dict() for item in self.issues]}


def _issue(code: str, path: list[str | int], message: str) -> WorkflowCompileError:
    return WorkflowCompileError([WorkflowIssue(code, path, message)])


def schema_at_path(schema: dict, path: list[str | int]) -> dict | None:
    current: Any = schema
    for part in path:
        if not isinstance(current, dict):
            return None
        schema_type = current.get("type")
        if schema_type == "array" and isinstance(part, int):
            current = current.get("items")
        else:
            properties = current.get("properties")
            if not isinstance(properties, dict) or str(part) not in properties:
                return None
            current = properties[str(part)]
    return current if isinstance(current, dict) else None


def _types(schema: dict) -> set[str]:
    value = schema.get("type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def schemas_compatible(source: dict, target: dict) -> bool:
    source_types, target_types = _types(source), _types(target)
    if not target_types:
        return True
    if not source_types:
        return False
    if source_types <= target_types:
        return True
    return source_types == {"integer"} and "number" in target_types


class WorkflowCompiler:
    def __init__(self, registry: StepRegistry | None = None):
        self.registry = registry or workflow_step_registry

    def compile(self, editor: dict, *, version: int) -> dict:
        if not isinstance(editor, dict):
            raise _issue("invalid_definition", [], "Workflow must be an object")
        key = editor.get("key")
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise _issue("invalid_key", ["key"], "Workflow key is invalid")
        input_schema = editor.get("input_schema", {"type": "object", "properties": {}})
        if not isinstance(input_schema, dict) or input_schema.get("type", "object") != "object":
            raise _issue("invalid_input_schema", ["input_schema"], "Workflow input schema must describe an object")
        input_properties = input_schema.get("properties", {})
        if not isinstance(input_properties, dict):
            raise _issue("invalid_input_schema", ["input_schema", "properties"], "Workflow input properties must be an object")
        for field_name, field_schema in input_properties.items():
            if not isinstance(field_name, str) or not _FIELD_KEY.fullmatch(field_name):
                raise _issue("invalid_input_name", ["input_schema", "properties", field_name],
                             "Input names must use lowercase letters, numbers, and underscores")
            if not isinstance(field_schema, dict):
                raise _issue("invalid_input_schema", ["input_schema", "properties", field_name],
                             "Every workflow input must have a schema")
        required = input_schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise _issue("invalid_required_inputs", ["input_schema", "required"], "Required inputs must be an array of names")
        unknown_required = set(required) - set(input_properties)
        if unknown_required:
            name = sorted(unknown_required)[0]
            raise _issue("unknown_required_input", ["input_schema", "required"], f"Required input '{name}' is not declared")
        editor_steps = editor.get("steps")
        if not isinstance(editor_steps, list) or not editor_steps:
            raise _issue("empty_workflow", ["steps"], "Add at least one workflow step")

        compiled_steps: list[dict] = []
        prior: dict[str, tuple[dict, bool]] = {}
        for index, step in enumerate(editor_steps):
            path = ["steps", index]
            if not isinstance(step, dict):
                raise _issue("invalid_step", path, "Step must be an object")
            invocation_key = step.get("key")
            if not isinstance(invocation_key, str) or not _STEP_KEY.fullmatch(invocation_key):
                raise _issue("invalid_step_key", path + ["key"], "Step key is invalid")
            if invocation_key in prior:
                raise _issue("duplicate_step_key", path + ["key"], f"Step key '{invocation_key}' is already used")
            step_type = step.get("step")
            step_version = step.get("step_version", 1)
            registered = self.registry.get(step_type, step_version) if isinstance(step_type, str) else None
            if registered is None:
                raise _issue("unknown_step", path + ["step"], f"Step type '{step_type}@{step_version}' is not deployed")
            spec = registered.spec
            bindings = step.get("bindings", {})
            if not isinstance(bindings, dict):
                raise _issue("invalid_bindings", path + ["bindings"], "Step bindings must be an object")
            properties = spec.input_schema.get("properties", {})
            properties = properties if isinstance(properties, dict) else {}
            unknown = set(bindings) - set(properties)
            if unknown:
                name = sorted(unknown)[0]
                raise _issue("unknown_input", path + ["bindings", name], f"'{name}' is not an input of {spec.key}")
            missing = set(spec.input_schema.get("required", [])) - set(bindings)
            if missing:
                name = sorted(missing)[0]
                raise _issue("missing_input", path + ["bindings", name], f"Required input '{name}' is not connected")

            compiled_inputs = {}
            for name, binding in bindings.items():
                compiled_inputs[name] = self._binding(
                    binding, properties.get(name, {}), input_schema, prior,
                    path + ["bindings", name],
                )
            when = self._condition(step.get("when"), input_schema, prior, path + ["when"])
            on_failure = step.get("on_failure", "stop")
            if on_failure not in {"stop", "continue"}:
                raise _issue("invalid_failure_policy", path + ["on_failure"], "Failure policy must be stop or continue")
            compiled = {
                "key": invocation_key,
                "step": spec.key,
                "step_version": spec.version,
                "inputs": compiled_inputs,
                "on_failure": on_failure,
            }
            if when is not None:
                compiled["when"] = when
            compiled_steps.append(compiled)
            prior[invocation_key] = (spec.output_schema, when is not None or on_failure == "continue")

        definition = {
            "key": key,
            "version": version,
            "description": str(editor.get("description", "")),
            "input_schema": copy.deepcopy(input_schema),
            "steps": compiled_steps,
        }
        try:
            return validate_workflow_definition(definition, self.registry, strict_bindings=True)
        except WorkflowCompileError:
            raise
        except WorkflowDefinitionError as exc:
            raise _issue("invalid_compiled_definition", [], str(exc)) from exc

    def _binding(self, binding: Any, target: dict, workflow_schema: dict,
                 prior: dict[str, tuple[dict, bool]], path: list[str | int]) -> Any:
        if not isinstance(binding, dict) or not isinstance(binding.get("source"), str):
            raise _issue("invalid_binding", path, "Choose a literal, workflow input, or earlier step output")
        source = binding["source"]
        if source == "literal":
            value = copy.deepcopy(binding.get("value"))
            try:
                validate_value_against_schema(value, target, "literal")
            except WorkflowDefinitionError as exc:
                raise _issue("invalid_literal", path, str(exc)) from exc
            return value
        if source == "first_available":
            candidates = binding.get("candidates")
            if not isinstance(candidates, list) or len(candidates) < 2:
                raise _issue("invalid_merge", path, "A branch merge needs at least two candidate outputs")
            return {"$first_available": [
                self._binding(candidate, target, workflow_schema, prior, path + ["candidates", index])
                for index, candidate in enumerate(candidates)
            ]}
        if source not in {"workflow_input", "step_output"}:
            raise _issue("invalid_binding_source", path + ["source"], f"Unknown binding source: {source}")
        raw_path = binding.get("path", [])
        if not isinstance(raw_path, list) or any(not isinstance(item, (str, int)) for item in raw_path):
            raise _issue("invalid_binding_path", path + ["path"], "Binding path must be an array")
        optional = binding.get("optional", False)
        if not isinstance(optional, bool):
            raise _issue("invalid_optional", path + ["optional"], "Optional must be a boolean")
        if source == "workflow_input":
            source_schema = schema_at_path(workflow_schema, raw_path)
            prefix = "$.input"
        else:
            source_step = binding.get("step_key")
            if source_step not in prior:
                raise _issue("invalid_step_reference", path + ["step_key"], "Only earlier step outputs may be selected")
            source_schema, may_be_missing = prior[source_step]
            source_schema = schema_at_path(source_schema, raw_path)
            prefix = f"$.steps.{source_step}.output"
            if may_be_missing and not optional:
                raise _issue("unsafe_step_reference", path, "This output may be absent; mark it optional or merge branch outputs")
        if source_schema is None:
            raise _issue("unknown_output_path", path + ["path"], "The selected source path is not declared by its schema")
        if not schemas_compatible(source_schema, target):
            raise _issue("incompatible_binding", path, "The selected output type is not compatible with this input")
        expression = {"$ref": prefix + "".join(f".{item}" for item in raw_path)}
        if optional:
            expression["$optional"] = True
        return expression

    def _condition(self, condition: Any, workflow_schema: dict,
                   prior: dict[str, tuple[dict, bool]], path: list[str | int]) -> dict | None:
        if condition is None:
            return None
        if not isinstance(condition, dict):
            raise _issue("invalid_condition", path, "Condition must be an object")
        operator = condition.get("op")
        if operator in {"all", "any"}:
            children = condition.get("conditions")
            if not isinstance(children, list) or not children:
                raise _issue("invalid_condition", path + ["conditions"], "Add at least one nested condition")
            return {"op": operator, "conditions": [
                self._condition(child, workflow_schema, prior, path + ["conditions", index])
                for index, child in enumerate(children)
            ]}
        if operator == "not":
            return {"op": "not", "condition": self._condition(condition.get("condition"), workflow_schema, prior, path + ["condition"])}
        if operator in {"exists", "is_true", "is_false"}:
            return {"op": operator, "value": self._operand(condition.get("value"), workflow_schema, prior, path + ["value"])}
        if operator in {"eq", "ne"}:
            left_editor, right_editor = condition.get("left"), condition.get("right")
            left_schema = self._operand_schema(left_editor, workflow_schema, prior)
            right_schema = self._operand_schema(right_editor, workflow_schema, prior)
            if left_schema and isinstance(right_editor, dict) and right_editor.get("source") == "literal":
                try:
                    validate_value_against_schema(right_editor.get("value"), left_schema, "condition literal")
                except WorkflowDefinitionError as exc:
                    raise _issue("incompatible_condition", path + ["right"], str(exc)) from exc
            if right_schema and isinstance(left_editor, dict) and left_editor.get("source") == "literal":
                try:
                    validate_value_against_schema(left_editor.get("value"), right_schema, "condition literal")
                except WorkflowDefinitionError as exc:
                    raise _issue("incompatible_condition", path + ["left"], str(exc)) from exc
            if left_schema and right_schema and not (
                    schemas_compatible(left_schema, right_schema)
                    or schemas_compatible(right_schema, left_schema)):
                raise _issue("incompatible_condition", path, "Condition values have incompatible types")
            return {"op": operator,
                    "left": self._operand(left_editor, workflow_schema, prior, path + ["left"]),
                    "right": self._operand(right_editor, workflow_schema, prior, path + ["right"])}
        raise _issue("invalid_condition_operator", path + ["op"], f"Unsupported condition operator: {operator}")

    def _operand(self, operand: Any, workflow_schema: dict,
                 prior: dict[str, tuple[dict, bool]], path: list[str | int]) -> Any:
        if not isinstance(operand, dict) or operand.get("source") == "literal":
            return copy.deepcopy(operand.get("value") if isinstance(operand, dict) else operand)
        source = operand.get("source")
        raw_path = operand.get("path", [])
        if not isinstance(raw_path, list):
            raise _issue("invalid_condition_path", path, "Condition source path must be an array")
        if source == "workflow_input":
            if schema_at_path(workflow_schema, raw_path) is None:
                raise _issue("unknown_condition_input", path, "Condition references an unknown workflow input")
            prefix = "$.input"
        elif source == "step_output":
            step_key = operand.get("step_key")
            if step_key not in prior or schema_at_path(prior[step_key][0], raw_path) is None:
                raise _issue("unknown_condition_output", path, "Condition must reference a declared earlier step output")
            prefix = f"$.steps.{step_key}.output"
        else:
            raise _issue("invalid_condition_source", path, "Choose a workflow input, earlier output, or literal")
        return {"$ref": prefix + "".join(f".{item}" for item in raw_path), "$optional": True}

    @staticmethod
    def _operand_schema(operand: Any, workflow_schema: dict,
                        prior: dict[str, tuple[dict, bool]]) -> dict | None:
        if not isinstance(operand, dict):
            return None
        raw_path = operand.get("path", [])
        if not isinstance(raw_path, list):
            return None
        if operand.get("source") == "workflow_input":
            return schema_at_path(workflow_schema, raw_path)
        if operand.get("source") == "step_output" and operand.get("step_key") in prior:
            return schema_at_path(prior[operand["step_key"]][0], raw_path)
        return None

from __future__ import annotations

import copy
import json
import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.workflows.registry import StepRegistry

_STEP_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MAX_DEFINITION_BYTES = 1024 * 1024
_MISSING = object()
_CONDITION_OPERATORS = {"eq", "ne", "exists", "is_true", "is_false", "all", "any", "not"}


class WorkflowDefinitionError(ValueError):
    pass


class WorkflowReferenceError(ValueError):
    pass


def _references(value: Any):
    if isinstance(value, dict):
        if "$ref" in value or "$optional" in value:
            yield value
        else:
            for child in value.values():
                yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _validate_condition(condition: Any, location: str) -> None:
    if not isinstance(condition, dict) or condition.get("op") not in _CONDITION_OPERATORS:
        raise WorkflowDefinitionError(f"{location} must be a structured condition")
    operator = condition["op"]
    allowed = {"op"}
    if operator in {"eq", "ne"}:
        allowed |= {"left", "right"}
        if "left" not in condition or "right" not in condition:
            raise WorkflowDefinitionError(f"{location} requires left and right operands")
    elif operator in {"exists", "is_true", "is_false"}:
        allowed.add("value")
        if "value" not in condition:
            raise WorkflowDefinitionError(f"{location} requires a value operand")
    elif operator in {"all", "any"}:
        allowed.add("conditions")
        children = condition.get("conditions")
        if not isinstance(children, list) or not children:
            raise WorkflowDefinitionError(f"{location}.conditions must not be empty")
        for index, child in enumerate(children):
            _validate_condition(child, f"{location}.conditions[{index}]")
    else:
        allowed.add("condition")
        _validate_condition(condition.get("condition"), f"{location}.condition")
    unknown = set(condition) - allowed
    if unknown:
        raise WorkflowDefinitionError(f"{location} has unknown properties: {', '.join(sorted(unknown))}")


def validate_workflow_definition(definition: dict, registry: StepRegistry | None = None,
                                 *, strict_bindings: bool = False) -> dict:
    from src.workflows.contracts import OnFailure
    from src.workflows.registry import workflow_step_registry

    registry = registry or workflow_step_registry
    if not isinstance(definition, dict):
        raise WorkflowDefinitionError("definition must be an object")
    if len(json.dumps(definition).encode()) > _MAX_DEFINITION_BYTES:
        raise WorkflowDefinitionError("definition exceeds the 1 MiB limit")
    steps = definition.get("steps")
    if not isinstance(steps, list) or not steps:
        raise WorkflowDefinitionError("definition.steps must contain at least one step")
    schema = definition.get("input_schema", {})
    if not isinstance(schema, dict):
        raise WorkflowDefinitionError("definition.input_schema must be an object")

    normalized = copy.deepcopy(definition)
    prior: set[str] = set()
    properties = schema.get("properties", {}) if isinstance(schema.get("properties", {}), dict) else {}
    for index, invocation in enumerate(normalized["steps"]):
        if not isinstance(invocation, dict):
            raise WorkflowDefinitionError(f"steps[{index}] must be an object")
        key = invocation.get("key")
        if not isinstance(key, str) or not _STEP_KEY.fullmatch(key):
            raise WorkflowDefinitionError(f"steps[{index}].key is invalid")
        if key in prior:
            raise WorkflowDefinitionError(f"duplicate step key: {key}")
        step_type = invocation.get("step", invocation.pop("action", None))
        step_version = invocation.get("step_version", 1)
        if not isinstance(step_version, int) or isinstance(step_version, bool) or step_version < 1:
            raise WorkflowDefinitionError(f"step '{key}'.step_version must be a positive integer")
        registered = registry.get(step_type, step_version) if isinstance(step_type, str) else None
        if registered is None:
            raise WorkflowDefinitionError(
                f"unknown step type for step '{key}': {step_type}@{step_version}")
        invocation["step"] = step_type
        invocation["step_version"] = step_version
        inputs = invocation.get("inputs", invocation.pop("with", {}))
        if not isinstance(inputs, dict):
            raise WorkflowDefinitionError(f"step '{key}'.inputs must be an object")
        invocation["inputs"] = inputs
        try:
            invocation["on_failure"] = OnFailure(invocation.get("on_failure", "stop")).value
        except (TypeError, ValueError):
            raise WorkflowDefinitionError(f"step '{key}'.on_failure must be 'stop' or 'continue'") from None

        if strict_bindings and "$ref" not in inputs:
            step_props = registered.spec.input_schema.get("properties", {})
            if isinstance(step_props, dict) and step_props:
                unknown = set(inputs) - set(step_props)
                missing = set(registered.spec.input_schema.get("required", [])) - set(inputs)
                if unknown:
                    raise WorkflowDefinitionError(f"step '{key}' configures unknown inputs: {', '.join(sorted(unknown))}")
                if missing:
                    raise WorkflowDefinitionError(f"step '{key}' is missing required inputs: {', '.join(sorted(missing))}")

        condition = invocation.get("when")
        if "run_if" in invocation:
            raise WorkflowDefinitionError(f"step '{key}'.run_if is no longer supported; use when")
        if condition is not None:
            _validate_condition(condition, f"step '{key}'.when")

        for expression in list(_references(inputs)) + list(_references(condition)):
            if not set(expression).issubset({"$ref", "$optional"}):
                raise WorkflowDefinitionError(f"invalid reference expression in step '{key}'")
            reference = expression.get("$ref")
            if not isinstance(reference, str) or not reference.startswith("$."):
                raise WorkflowDefinitionError(f"invalid reference in step '{key}': {reference}")
            if expression.get("$optional", True) is not True:
                raise WorkflowDefinitionError(f"optional reference in step '{key}' must use true")
            parts = reference[2:].split(".")
            if parts[0] == "input":
                if strict_bindings and len(parts) > 1 and parts[1] not in properties:
                    raise WorkflowDefinitionError(f"step '{key}' references undeclared workflow input: {reference}")
            elif len(parts) < 3 or parts[0] != "steps" or parts[2] != "output" or parts[1] not in prior:
                raise WorkflowDefinitionError(f"step '{key}' may only reference earlier step output: {reference}")
        prior.add(key)
    return normalized


def _condition_operand(value: Any, context: dict) -> Any:
    if isinstance(value, dict) and "$ref" in value:
        try:
            return resolve_reference(value["$ref"], context)
        except WorkflowReferenceError:
            if value.get("$optional") is True:
                return _MISSING
            raise
    return copy.deepcopy(value)


def evaluate_condition(condition: dict, context: dict) -> bool:
    operator = condition["op"]
    if operator in {"all", "any"}:
        values = (evaluate_condition(item, context) for item in condition["conditions"])
        return all(values) if operator == "all" else any(values)
    if operator == "not":
        return not evaluate_condition(condition["condition"], context)
    if operator == "exists":
        return _condition_operand(condition["value"], context) is not _MISSING
    if operator in {"is_true", "is_false"}:
        value = _condition_operand(condition["value"], context)
        return value is (operator == "is_true")
    left = _condition_operand(condition["left"], context)
    right = _condition_operand(condition["right"], context)
    if left is _MISSING or right is _MISSING:
        return False
    return left == right if operator == "eq" else left != right


def should_run_step(step: dict, context: dict) -> bool:
    condition = step.get("when")
    return condition is None or evaluate_condition(condition, context)


def resolve_reference(reference: str, context: dict) -> Any:
    current: Any = context
    if not isinstance(reference, str) or not reference.startswith("$."):
        raise WorkflowReferenceError(f"Invalid workflow reference: {reference}")
    for part in reference[2:].split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise WorkflowReferenceError(f"Workflow reference not found: {reference}")
    return copy.deepcopy(current)


def _resolve(value: Any, context: dict) -> Any:
    if isinstance(value, dict):
        if "$first_available" in value and set(value) == {"$first_available"}:
            candidates = value["$first_available"]
            if not isinstance(candidates, list) or not candidates:
                raise WorkflowReferenceError("$first_available requires at least one candidate")
            for candidate in candidates:
                try:
                    resolved = _resolve(candidate, context)
                except WorkflowReferenceError:
                    continue
                if resolved is not _MISSING:
                    return resolved
            return _MISSING
        if "$ref" in value and set(value).issubset({"$ref", "$optional"}):
            try:
                return resolve_reference(value["$ref"], context)
            except WorkflowReferenceError:
                if value.get("$optional") is True:
                    return _MISSING
                raise
        result = {}
        for key, child in value.items():
            resolved = _resolve(child, context)
            if resolved is not _MISSING:
                result[key] = resolved
        return result
    if isinstance(value, list):
        result = [_resolve(child, context) for child in value]
        return [child for child in result if child is not _MISSING]
    return copy.deepcopy(value)


def resolve_step_input(value: Any, context: dict) -> Any:
    result = _resolve(value, context)
    return {} if result is _MISSING else result


def validate_value_against_schema(value: Any, schema: dict, location: str = "value") -> None:
    """Validate the JSON-Schema subset used by workflow contracts."""
    if not schema:
        return
    expected = schema.get("type")
    matches = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if expected in matches and not matches[expected](value):
        raise WorkflowDefinitionError(f"{location} must be of type {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise WorkflowDefinitionError(f"{location} must be one of {schema['enum']}")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                raise WorkflowDefinitionError(f"{location}.{name} is required")
        props = schema.get("properties", {})
        if isinstance(props, dict):
            for name, child in value.items():
                if name in props:
                    validate_value_against_schema(child, props[name], f"{location}.{name}")
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(props)
            if unknown:
                raise WorkflowDefinitionError(f"{location} has unknown properties: {', '.join(sorted(unknown))}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, child in enumerate(value):
            validate_value_against_schema(child, schema["items"], f"{location}[{index}]")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise WorkflowDefinitionError(f"{location} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise WorkflowDefinitionError(f"{location} must be <= {schema['maximum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise WorkflowDefinitionError(f"{location} is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise WorkflowDefinitionError(f"{location} is too long")

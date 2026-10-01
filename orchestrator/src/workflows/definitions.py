from __future__ import annotations

import copy
import importlib
import pkgutil
import re
from dataclasses import dataclass

from src.services.workflows.workflow_definition_service import validate_workflow_definition
from .contracts import OnFailure
from .registry import StepRegistry, workflow_step_registry
from .step import RegisteredStep

_WORKFLOW_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,119}$")


def input_ref(path: str = "", *, optional: bool = False) -> dict:
    value = {"$ref": "$.input" + (f".{path}" if path else "")}
    if optional:
        value["$optional"] = True
    return value


def step_output_ref(step_key: str, path: str = "", *, optional: bool = False) -> dict:
    value = {"$ref": f"$.steps.{step_key}.output" + (f".{path}" if path else "")}
    if optional:
        value["$optional"] = True
    return value


def input_flag(name: str, default: bool = True) -> dict:
    if not name or not isinstance(default, bool):
        raise ValueError("input_flag requires a name and boolean default")
    return {"input": name, "equals": True, "default": default}


@dataclass(frozen=True)
class WorkflowStepInvocation:
    key: str
    step_type: str
    inputs: dict | None
    run_if: dict | None = None
    on_failure: OnFailure = OnFailure.STOP


class Workflow:
    def __init__(self, key: str, *, version: int, description: str = "",
                 input_schema: dict | None = None,
                 step_registry: StepRegistry = workflow_step_registry):
        if not isinstance(key, str) or not _WORKFLOW_KEY.fullmatch(key):
            raise ValueError(f"Invalid workflow key: {key}")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError("Workflow version must be a positive integer")
        self.key, self.version, self.description = key, version, description
        self._declared_input_schema = copy.deepcopy(input_schema)
        self.input_schema = copy.deepcopy(input_schema or {"type": "object"})
        self._step_registry = step_registry
        self._steps: list[WorkflowStepInvocation] = []
        self._compiled: dict | None = None

    def add_step(self, registered_step: RegisteredStep, *, key: str | None = None,
                 inputs: dict | None = None, run_if: dict | None = None,
                 on_failure: OnFailure = OnFailure.STOP) -> "Workflow":
        if self._compiled is not None:
            raise ValueError(f"Workflow is already registered: {self.key}")
        if self._step_registry.get(registered_step.spec.key) is not registered_step:
            raise ValueError(f"Workflow step is not registered: {registered_step.spec.key}")
        invocation_key = key or registered_step.spec.key.rsplit(".", 1)[-1].replace("-", "_")
        self._steps.append(WorkflowStepInvocation(invocation_key, registered_step.spec.key,
                                                  copy.deepcopy(inputs), copy.deepcopy(run_if), on_failure))
        return self

    def definition(self) -> dict:
        if self._compiled is not None:
            return copy.deepcopy(self._compiled)
        compiled_steps = []
        previous: list[tuple[str, RegisteredStep]] = []
        inferred_properties: dict = {}
        inferred_required: list[str] = []
        for item in self._steps:
            registered = self._step_registry.get(item.step_type)
            inputs = copy.deepcopy(item.inputs)
            if inputs is None:
                properties = registered.spec.input_schema.get("properties", {})
                required = set(registered.spec.input_schema.get("required", []))
                if not properties:
                    inputs = input_ref()
                else:
                    inputs = {}
                    for name, schema in properties.items():
                        producers = [
                            (step_key, step_def) for step_key, step_def in previous
                            if name in step_def.spec.output_schema.get("properties", {})
                        ]
                        if len(producers) > 1:
                            raise ValueError(
                                f"step '{item.key}' input '{name}' has multiple earlier producers"
                            )
                        optional = name not in required
                        if producers:
                            inputs[name] = step_output_ref(producers[0][0], name, optional=optional)
                        else:
                            inputs[name] = input_ref(name, optional=optional)
                            inferred_properties.setdefault(name, copy.deepcopy(schema))
                            if not optional and name not in inferred_required:
                                inferred_required.append(name)
            invocation = {"key": item.key, "step": item.step_type, "inputs": inputs,
                          "on_failure": item.on_failure.value}
            if item.run_if is not None:
                invocation["run_if"] = copy.deepcopy(item.run_if)
                flag = item.run_if.get("input")
                if self._declared_input_schema is None and flag:
                    inferred_properties.setdefault(flag, {"type": "boolean", "default": item.run_if.get("default", False)})
            compiled_steps.append(invocation)
            previous.append((item.key, registered))

        input_schema = copy.deepcopy(self.input_schema)
        if self._declared_input_schema is None and inferred_properties:
            input_schema = {
                "type": "object",
                "properties": inferred_properties,
                "additionalProperties": False,
            }
            if inferred_required:
                input_schema["required"] = inferred_required
        definition = {
            "key": self.key,
            "version": self.version,
            "description": self.description,
            "input_schema": input_schema,
            "steps": compiled_steps,
        }
        return definition

    def register(self, registry: "WorkflowRegistry | None" = None) -> "Workflow":
        return (registry or workflow_registry).register(self)

    def to_dict(self) -> dict:
        return self.definition()


class WorkflowRegistry:
    def __init__(self, step_registry: StepRegistry = workflow_step_registry):
        self._workflows: dict[str, Workflow] = {}
        self.step_registry = step_registry

    def register(self, item: Workflow) -> Workflow:
        if item.key in self._workflows:
            raise ValueError(f"Workflow is already registered: {item.key}")
        item._compiled = validate_workflow_definition(item.definition(), self.step_registry,
                                                       strict_bindings=True)
        item.input_schema = copy.deepcopy(item._compiled["input_schema"])
        self._workflows[item.key] = item
        return item

    def get(self, key: str) -> Workflow | None:
        return self._workflows.get(key)

    def list(self) -> list[Workflow]:
        return sorted(self._workflows.values(), key=lambda item: item.key)


workflow_registry = WorkflowRegistry()


@dataclass(frozen=True)
class WorkflowStepUse:
    registered_step: RegisteredStep
    key: str | None = None
    inputs: dict | None = None
    run_if: dict | None = None
    on_failure: OnFailure = OnFailure.STOP


def use(registered_step: RegisteredStep, *, key: str | None = None,
        inputs: dict | None = None, run_if: dict | None = None,
        on_failure: OnFailure = OnFailure.STOP) -> WorkflowStepUse:
    return WorkflowStepUse(registered_step, key, copy.deepcopy(inputs), copy.deepcopy(run_if), on_failure)


def workflow(key: str, *steps: RegisteredStep | WorkflowStepUse, version: int,
             description: str = "", input_schema: dict | None = None,
             registry: WorkflowRegistry | None = None) -> Workflow:
    target = registry or workflow_registry
    item = Workflow(key, version=version, description=description,
                    input_schema=input_schema, step_registry=target.step_registry)
    for configured in (step if isinstance(step, WorkflowStepUse) else use(step) for step in steps):
        item.add_step(configured.registered_step, key=configured.key, inputs=configured.inputs,
                      run_if=configured.run_if, on_failure=configured.on_failure)
    return item.register(target)


def discover_workflows() -> None:
    package = importlib.import_module(__package__)
    prefix = f"{__package__}."
    names = [module.name for module in pkgutil.walk_packages(package.__path__, prefix)
             if module.name != __name__]
    modules = [name for suffix in (".steps", ".definitions")
               for name in sorted(names) if name.endswith(suffix)]
    for module in modules:
        importlib.import_module(module)


# Built-ins are imported explicitly to avoid discovery import ordering surprises.
from .core import steps as _core_steps  # noqa: E402,F401

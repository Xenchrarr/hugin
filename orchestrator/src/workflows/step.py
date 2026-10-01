from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Protocol

from .contracts import StepContext, StepHandler, StepReturn

if TYPE_CHECKING:
    from .registry import StepRegistry


class ExecutionPolicy(Protocol):
    def execute(self, handler: StepHandler, context: StepContext, inputs: dict) -> StepReturn: ...


class DirectExecution:
    def execute(self, handler: StepHandler, context: StepContext, inputs: dict) -> StepReturn:
        return handler(context, inputs)


DIRECT_EXECUTION = DirectExecution()


@dataclass(frozen=True, slots=True)
class StepSpec:
    key: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    idempotent: bool = False

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "description": self.description,
            "input_schema": copy.deepcopy(self.input_schema),
            "output_schema": copy.deepcopy(self.output_schema),
            "idempotent": self.idempotent,
        }


@dataclass(frozen=True, slots=True)
class RegisteredStep:
    spec: StepSpec
    handler: StepHandler = field(repr=False, compare=False)
    execution: ExecutionPolicy = field(default=DIRECT_EXECUTION, repr=False, compare=False)

    def execute(self, context: StepContext, inputs: dict) -> StepReturn:
        return self.execution.execute(self.handler, context, inputs)

    def to_dict(self) -> dict:
        return self.spec.to_dict()


def step(
    key: str,
    *,
    description: str = "",
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    idempotent: bool = False,
    execution: ExecutionPolicy = DIRECT_EXECUTION,
    registry: StepRegistry | None = None,
) -> Callable[[StepHandler], RegisteredStep]:
    def decorator(handler: StepHandler) -> RegisteredStep:
        from .registry import workflow_step_registry
        item = RegisteredStep(
            StepSpec(key, description, copy.deepcopy(input_schema or {}),
                     copy.deepcopy(output_schema or {}), idempotent),
            handler,
            execution,
        )
        return (registry or workflow_step_registry).register(item)
    return decorator

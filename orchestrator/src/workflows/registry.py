from __future__ import annotations

from .step import RegisteredStep


class StepRegistry:
    def __init__(self):
        self._steps: dict[str, RegisteredStep] = {}

    def register(self, item: RegisteredStep) -> RegisteredStep:
        if not isinstance(item, RegisteredStep):
            raise TypeError("StepRegistry.register requires a RegisteredStep")
        key = item.spec.key
        if not key or key in self._steps:
            raise ValueError(f"Workflow step is missing or already registered: {key}")
        if "<locals>" in getattr(item.handler, "__qualname__", ""):
            raise ValueError(f"Workflow step handlers must be module-level functions: {key}")
        self._steps[key] = item
        return item

    def get(self, key: str) -> RegisteredStep | None:
        return self._steps.get(key)

    def list(self) -> list[RegisteredStep]:
        return sorted(self._steps.values(), key=lambda item: item.spec.key)


workflow_step_registry = StepRegistry()

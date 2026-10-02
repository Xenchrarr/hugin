from __future__ import annotations

from .step import RegisteredStep


class StepRegistry:
    def __init__(self):
        self._steps: dict[tuple[str, int], RegisteredStep] = {}

    def register(self, item: RegisteredStep) -> RegisteredStep:
        if not isinstance(item, RegisteredStep):
            raise TypeError("StepRegistry.register requires a RegisteredStep")
        key = (item.spec.key, item.spec.version)
        if not item.spec.key or not isinstance(item.spec.version, int) or item.spec.version < 1 or key in self._steps:
            raise ValueError(f"Workflow step is missing, invalid, or already registered: {key}")
        if "<locals>" in getattr(item.handler, "__qualname__", ""):
            raise ValueError(f"Workflow step handlers must be module-level functions: {key}")
        self._validate_contract(item.spec.input_schema, f"{item.spec.key} input")
        self._validate_contract(item.spec.output_schema, f"{item.spec.key} output")
        self._steps[key] = item
        return item

    @staticmethod
    def _validate_contract(schema: dict, label: str) -> None:
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError(f"{label} schema must be an object schema")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            raise ValueError(f"{label} schema must declare a properties map")
        additional = schema.get("additionalProperties")
        if not isinstance(additional, (bool, dict)):
            raise ValueError(f"{label} schema must declare its additionalProperties policy")
        required = schema.get("required", [])
        if (not isinstance(required, list) or any(not isinstance(name, str) for name in required)
                or not set(required).issubset(properties)):
            raise ValueError(f"{label} schema has invalid required properties")

    def get(self, key: str, version: int | None = None) -> RegisteredStep | None:
        if version is not None:
            return self._steps.get((key, version))
        matches = [item for (item_key, _), item in self._steps.items() if item_key == key]
        return max(matches, key=lambda item: item.spec.version) if matches else None

    def list(self) -> list[RegisteredStep]:
        return sorted(self._steps.values(), key=lambda item: (item.spec.key, item.spec.version))


workflow_step_registry = StepRegistry()

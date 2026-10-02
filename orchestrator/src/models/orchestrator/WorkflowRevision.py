from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WorkflowRevision:
    id: str
    workflow_id: str
    key: str
    name: str
    description: str
    version: int | None
    state: str
    editor_definition: dict = field(default_factory=dict)
    compiled_definition: dict = field(default_factory=dict)
    lock_version: int = 1
    archived: bool = False
    created_at: datetime | None = None
    published_at: datetime | None = None

    @property
    def input_schema(self) -> dict:
        return self.compiled_definition.get(
            "input_schema", self.editor_definition.get("input_schema", {"type": "object"}))

    @property
    def steps(self) -> list[dict]:
        return self.compiled_definition.get("steps", self.editor_definition.get("steps", []))

    def definition(self) -> dict:
        return copy.deepcopy(self.compiled_definition)

    def to_dict(self, *, include_editor: bool = False) -> dict:
        payload = self.definition() if self.compiled_definition else {
            "key": self.key,
            "version": self.version,
            "description": self.description,
            "input_schema": copy.deepcopy(self.input_schema),
            "steps": copy.deepcopy(self.steps),
        }
        payload.update({
            "id": self.workflow_id,
            "revision_id": self.id,
            "name": self.name,
            "state": self.state,
            "lock_version": self.lock_version,
            "archived": self.archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        })
        if include_editor:
            payload["editor_definition"] = copy.deepcopy(self.editor_definition)
        return payload

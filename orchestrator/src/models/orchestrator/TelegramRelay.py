from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TelegramRelayDestination:
    id: int
    name: str
    type: str
    config: dict
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "config": self.config,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_db_row(row) -> TelegramRelayDestination:
        config = row[3]
        if isinstance(config, str):
            config = json.loads(config)
        return TelegramRelayDestination(
            id=row[0],
            name=row[1],
            type=row[2],
            config=config or {},
            enabled=bool(row[4]),
            created_at=row[5],
            updated_at=row[6],
        )

    @staticmethod
    def from_dict(obj: dict) -> TelegramRelayDestination:
        return TelegramRelayDestination(
            id=obj.get("id", 0),
            name=obj.get("name", ""),
            type=obj.get("type", "webhook"),
            config=obj.get("config", {}),
            enabled=bool(obj.get("enabled", True)),
        )


@dataclass
class TelegramRelayRule:
    id: int
    name: str
    priority: int
    enabled: bool
    continue_on_match: bool
    conditions: Optional[dict]
    actions: list[dict]
    is_preset: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "enabled": self.enabled,
            "continue_on_match": self.continue_on_match,
            "conditions": self.conditions,
            "actions": self.actions,
            "is_preset": self.is_preset,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_db_row(row) -> TelegramRelayRule:
        conditions = row[5]
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        actions = row[6]
        if isinstance(actions, str):
            actions = json.loads(actions)
        return TelegramRelayRule(
            id=row[0],
            name=row[1],
            priority=row[2],
            enabled=bool(row[3]),
            continue_on_match=bool(row[4]),
            conditions=conditions,
            actions=actions or [],
            is_preset=bool(row[7]),
            created_at=row[8],
            updated_at=row[9],
        )

    @staticmethod
    def from_dict(obj: dict) -> TelegramRelayRule:
        return TelegramRelayRule(
            id=obj.get("id", 0),
            name=obj.get("name", ""),
            priority=obj.get("priority", 100),
            enabled=bool(obj.get("enabled", True)),
            continue_on_match=bool(obj.get("continue_on_match", False)),
            conditions=obj.get("conditions"),
            actions=obj.get("actions", []),
            is_preset=bool(obj.get("is_preset", False)),
        )

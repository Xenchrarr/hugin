from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        return json.loads(value)
    return value


@dataclass
class MessageRelayEndpoint:
    id: int
    key: str
    name: str
    type: str
    enabled: bool = True
    capabilities: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self, include_config: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "capabilities": self.capabilities,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_config:
            result["config"] = self.config
        return result

    @staticmethod
    def from_db_row(row) -> "MessageRelayEndpoint":
        return MessageRelayEndpoint(
            id=int(row[0]),
            key=row[1],
            name=row[2],
            type=row[3],
            enabled=bool(row[4]),
            capabilities=list(_json_value(row[5], [])),
            config=dict(_json_value(row[6], {})),
            created_at=row[7],
            updated_at=row[8],
        )

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> "MessageRelayEndpoint":
        return MessageRelayEndpoint(
            id=int(obj.get("id") or 0),
            key=str(obj.get("key") or "").strip(),
            name=str(obj.get("name") or "").strip(),
            type=str(obj.get("type") or "").strip().lower(),
            enabled=bool(obj.get("enabled", True)),
            capabilities=list(obj.get("capabilities") or []),
            config=dict(obj.get("config") or {}),
        )


@dataclass
class MessageRelayTarget:
    endpoint: MessageRelayEndpoint
    enabled: bool = True
    transform: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_config: bool = True) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint.to_dict(include_config=include_config),
            "enabled": self.enabled,
            "transform": self.transform,
        }


@dataclass
class MessageRelayRoute:
    id: int
    key: str
    name: str
    enabled: bool = True
    match_all_sources: bool = False
    filter: Optional[dict[str, Any]] = None
    is_preset: bool = False
    sources: list[MessageRelayEndpoint] = field(default_factory=list)
    targets: list[MessageRelayTarget] = field(default_factory=list)
    source_endpoint_ids: list[int] = field(default_factory=list, repr=False)
    target_specs: list[dict[str, Any]] = field(default_factory=list, repr=False)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self, include_config: bool = True) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "enabled": self.enabled,
            "match_all_sources": self.match_all_sources,
            "filter": self.filter,
            "is_preset": self.is_preset,
            "sources": [source.to_dict(include_config=False) for source in self.sources],
            "targets": [target.to_dict(include_config=include_config) for target in self.targets],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_db_row(row) -> "MessageRelayRoute":
        return MessageRelayRoute(
            id=int(row[0]),
            key=row[1],
            name=row[2],
            enabled=bool(row[3]),
            match_all_sources=bool(row[4]),
            filter=_json_value(row[5], None),
            is_preset=bool(row[6]),
            created_at=row[7],
            updated_at=row[8],
        )

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> "MessageRelayRoute":
        route = MessageRelayRoute(
            id=int(obj.get("id") or 0),
            key=str(obj.get("key") or "").strip(),
            name=str(obj.get("name") or "").strip(),
            enabled=bool(obj.get("enabled", True)),
            match_all_sources=bool(obj.get("match_all_sources", False)),
            filter=obj.get("filter"),
            is_preset=bool(obj.get("is_preset", False)),
        )
        route.source_endpoint_ids = [int(value) for value in obj.get("source_endpoint_ids", [])]
        route.target_specs = [dict(value) for value in obj.get("targets", [])]
        return route

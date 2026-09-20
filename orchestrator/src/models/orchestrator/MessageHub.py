from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


def _json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        value = json.loads(value)
    return dict(value)


@dataclass
class MessageGateway:
    id: int
    key: str
    name: str
    type: str
    enabled: bool
    status: str
    config: dict[str, Any]
    consecutive_failures: int
    consecutive_successes: int
    last_error: Optional[str]
    last_checked_at: Optional[datetime]
    last_healthy_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_db_row(row) -> "MessageGateway":
        values = list(row)
        values[4] = bool(values[4])
        values[6] = _json_object(values[6])
        return MessageGateway(*values)

    def to_dict(self, include_config: bool = False) -> dict[str, Any]:
        result = {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_error": self.last_error,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_healthy_at": self.last_healthy_at.isoformat() if self.last_healthy_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_config:
            result["config"] = self.config
        return result


@dataclass
class HubMessage:
    id: int
    direction: str
    kind: str
    source_gateway_id: Optional[int]
    source_endpoint_id: Optional[int]
    external_id: Optional[str]
    conversation_key: Optional[str]
    payload: dict[str, Any]
    metadata: dict[str, Any]
    priority: int
    idempotency_key: Optional[str]
    created_at: datetime
    expires_at: datetime

    @staticmethod
    def from_db_row(row) -> "HubMessage":
        values = list(row)
        values[7] = _json_object(values[7])
        values[8] = _json_object(values[8])
        return HubMessage(*values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "direction": self.direction,
            "kind": self.kind,
            "source_gateway_id": self.source_gateway_id,
            "source_endpoint_id": self.source_endpoint_id,
            "external_id": self.external_id,
            "conversation_key": self.conversation_key,
            "payload": self.payload,
            "metadata": self.metadata,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass
class MessageAttachment:
    id: int
    message_id: int
    position: int
    content_type: str
    filename: Optional[str]
    content: bytes
    size_bytes: int
    sha256: str
    created_at: datetime

    @staticmethod
    def from_db_row(row) -> "MessageAttachment":
        values = list(row)
        values[5] = bytes(values[5])
        return MessageAttachment(*values)

    def to_dict(self, include_content: bool = False) -> dict[str, Any]:
        result = {
            "id": self.id,
            "message_id": self.message_id,
            "position": self.position,
            "content_type": self.content_type,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_at": self.created_at.isoformat(),
        }
        if include_content:
            result["content"] = self.content
        return result


@dataclass
class MessageDelivery:
    id: int
    message_id: int
    gateway_id: int
    target_endpoint_id: Optional[int]
    route_id: Optional[int]
    address: dict[str, Any]
    payload: dict[str, Any]
    status: str
    recovery_policy: str
    priority: int
    attempts: int
    max_attempts: int
    available_at: datetime
    lease_token: Optional[str]
    leased_until: Optional[datetime]
    accepted_at: Optional[datetime]
    expired_at: Optional[datetime]
    recovery_notified_at: Optional[datetime]
    last_error: Optional[str]
    idempotency_key: Optional[str]
    dispatch_token: str
    created_at: datetime
    updated_at: datetime
    recipient_key: str
    acknowledged_at: Optional[datetime]
    gateway_key: Optional[str] = None
    gateway_type: Optional[str] = None
    gateway_config: Optional[dict[str, Any]] = None

    @staticmethod
    def from_db_row(row, include_gateway: bool = False) -> "MessageDelivery":
        values = list(row)
        values[5] = _json_object(values[5])
        values[6] = _json_object(values[6])
        if include_gateway:
            values[27] = _json_object(values[27])
        return MessageDelivery(*values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "gateway_id": self.gateway_id,
            "gateway_key": self.gateway_key,
            "gateway_type": self.gateway_type,
            "recipient_key": self.recipient_key,
            "target_endpoint_id": self.target_endpoint_id,
            "route_id": self.route_id,
            "address": self.address,
            "payload": self.payload,
            "status": self.status,
            "recovery_policy": self.recovery_policy,
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "available_at": self.available_at.isoformat(),
            "leased_until": self.leased_until.isoformat() if self.leased_until else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
            "recovery_notified_at": (
                self.recovery_notified_at.isoformat() if self.recovery_notified_at else None
            ),
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
            "last_error": self.last_error,
            "dispatch_token": self.dispatch_token,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

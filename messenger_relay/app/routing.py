from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.models import NormalizedMessage

logger = logging.getLogger(__name__)


def _numeric_eq(value: Any, reference: Any) -> bool:
    if value == reference:
        return True
    try:
        return type(value) is not type(reference) and int(value) == int(reference)
    except (TypeError, ValueError):
        return False


def matches_condition(condition: dict[str, Any] | None, message: NormalizedMessage) -> bool:
    if not condition:
        return True
    if "all" in condition:
        return all(matches_condition(item, message) for item in condition["all"])
    if "any" in condition:
        return any(matches_condition(item, message) for item in condition["any"])
    if "not" in condition:
        return not matches_condition(condition["not"], message)

    field = condition.get("field")
    operator = condition.get("op")
    reference = condition.get("value")
    if not field or not operator:
        return False
    value = getattr(message, str(field), None)
    operations = {
        "eq": lambda: _numeric_eq(value, reference),
        "neq": lambda: not _numeric_eq(value, reference),
        "in": lambda: any(_numeric_eq(value, item) for item in reference),
        "not_in": lambda: not any(_numeric_eq(value, item) for item in reference),
        "contains": lambda: isinstance(value, str) and str(reference) in value,
        "regex": lambda: isinstance(value, str) and bool(re.search(str(reference), value)),
        "exists": lambda: value is not None,
        "gt": lambda: value is not None and value > reference,
        "lt": lambda: value is not None and value < reference,
    }
    if operator not in operations:
        raise ValueError(f"Unknown condition operator: {operator!r}")
    return bool(operations[operator]())


@dataclass(frozen=True)
class Target:
    endpoint_id: str
    endpoint_key: str
    endpoint_type: str
    config: dict[str, Any]
    transform: dict[str, Any]
    route_id: int | None


@dataclass(frozen=True)
class Route:
    name: str
    condition: dict[str, Any] | None
    targets: list[Target]


def compile_routes(raw: dict[str, Any], source_key: str) -> list[Route]:
    endpoints = {str(item.get("id")): item for item in raw.get("endpoints", [])}
    result: list[Route] = []
    for route in raw.get("routes", []):
        if not route.get("enabled", True):
            continue
        sources = route.get("sources") or []
        if not route.get("match_all_sources", False) and not any(
            source.get("key") == source_key for source in sources
        ):
            continue
        targets: list[Target] = []
        for target_spec in route.get("targets") or []:
            endpoint = target_spec.get("endpoint") or {}
            endpoint = endpoints.get(str(endpoint.get("id")), endpoint)
            if not target_spec.get("enabled", True) or not endpoint.get("enabled", True):
                continue
            endpoint_type = str(endpoint.get("type") or "")
            if endpoint_type not in {"sms", "telegram", "reticulum", "webhook"}:
                continue
            targets.append(
                Target(
                    endpoint_id=str(endpoint.get("id") or ""),
                    endpoint_key=str(endpoint.get("key") or endpoint.get("id") or ""),
                    endpoint_type=endpoint_type,
                    config=dict(endpoint.get("config") or {}),
                    transform=dict(target_spec.get("transform") or {}),
                    route_id=int(route["id"]) if route.get("id") else None,
                )
            )
        if targets:
            result.append(
                Route(
                    name=str(route.get("name") or route.get("key") or "unnamed"),
                    condition=route.get("filter"),
                    targets=targets,
                )
            )
    return result


class RouteDispatcher:
    def __init__(self, orchestrator_url: str, service_key: str) -> None:
        self._base = orchestrator_url.rstrip("/")
        headers = {"X-Service-Key": service_key} if service_key else {}
        self._client = httpx.AsyncClient(headers=headers, timeout=30)

    async def fetch_config(self) -> dict[str, Any]:
        response = await self._client.get(f"{self._base}/api/telegram_relay/config")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _display_text(message: NormalizedMessage) -> str:
        body = message.text or message.caption or f"<{message.media_type or 'message'}>"
        labels = [item for item in (message.chat_title, message.sender_name) if item]
        if message.chat_type == "private" and labels:
            labels = labels[:1]
        return f"{' / '.join(labels)}: {body}" if labels else body

    async def dispatch(self, message: NormalizedMessage, target: Target) -> None:
        transformed = message.redacted(target.transform.get("redact") or [])
        payload = transformed.to_payload(
            include_fields=target.transform.get("include_fields"),
            exclude_fields=target.transform.get("exclude_fields"),
        )
        target_id = int(target.endpoint_id) if target.endpoint_id.isdigit() else None
        delivery: dict[str, Any]
        if target.endpoint_type == "sms":
            phone = str(target.config.get("phone") or "").strip()
            if not phone:
                raise ValueError(f"SMS endpoint {target.endpoint_key!r} has no phone")
            delivery = {
                "gateway_key": "sms-main",
                "address": {"phone": phone},
                "recovery_policy": target.config.get("recovery_policy", "digest_hold"),
            }
            payload = {"text": f"fb: {self._display_text(transformed)}"}
        elif target.endpoint_type == "telegram":
            chat_id = target.config.get("chat_id")
            if chat_id is None:
                raise ValueError(f"Telegram endpoint {target.endpoint_key!r} has no chat_id")
            delivery = {
                "gateway_key": "telegram-main",
                "address": {"chat_id": int(chat_id)},
                "recovery_policy": target.config.get("recovery_policy", "replay"),
            }
            payload = {"text": self._display_text(transformed)}
        elif target.endpoint_type == "reticulum":
            destination_hash = str(
                target.config.get("destination_hash") or ""
            ).strip().lower()
            if not destination_hash:
                raise ValueError(
                    f"Reticulum endpoint {target.endpoint_key!r} has no destination_hash"
                )
            delivery = {
                "gateway_key": "reticulum-main",
                "address": {
                    "destination_hash": destination_hash,
                    "delivery_method": target.config.get("delivery_method", "direct"),
                },
                "recovery_policy": target.config.get("recovery_policy", "replay"),
            }
            payload = {"text": self._display_text(transformed)}
        else:
            url = str(target.config.get("url") or "").strip()
            if not url:
                raise ValueError(f"Webhook endpoint {target.endpoint_key!r} has no URL")
            delivery = {
                "gateway_key": "webhook-main",
                "address": {
                    "url": url,
                    "headers": target.config.get("headers") or {},
                    "timeout": target.config.get("timeout", 15),
                },
                "recovery_policy": target.config.get("recovery_policy", "replay"),
            }
        if target_id is not None:
            delivery["target_endpoint_id"] = target_id
        if target.route_id is not None:
            delivery["route_id"] = target.route_id
        delivery["idempotency_key"] = f"messenger:{message.message_id}:{target.endpoint_key}"
        body = {
            "direction": "outbound",
            "kind": "text",
            "source_gateway_key": "messenger-main",
            "external_id": message.message_id,
            "conversation_key": message.chat_id,
            "payload": payload,
            "metadata": {
                "source_type": "messenger",
                "source_label": message.chat_title or message.sender_name or "Messenger",
                "thread_id": message.chat_id,
                "matrix_room_id": message.room_id,
            },
            "idempotency_key": f"messenger:{message.message_id}",
            "deliveries": [delivery],
        }
        response = await self._client.post(f"{self._base}/api/message-hub/messages", json=body)
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()

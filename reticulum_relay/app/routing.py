from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any

import requests

from app.normalizer import NormalizedMessage
from app.state import StateStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Target:
    endpoint_id: int | None
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


def _equivalent(value: Any, reference: Any) -> bool:
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
    field = str(condition.get("field") or "")
    operator = str(condition.get("op") or "")
    reference = condition.get("value")
    value = getattr(message, field, None)
    operations = {
        "eq": lambda: _equivalent(value, reference),
        "neq": lambda: not _equivalent(value, reference),
        "in": lambda: any(_equivalent(value, item) for item in reference),
        "not_in": lambda: not any(_equivalent(value, item) for item in reference),
        "contains": lambda: isinstance(value, str) and str(reference) in value,
        "regex": lambda: isinstance(value, str) and bool(re.search(str(reference), value)),
        "exists": lambda: value is not None,
        "gt": lambda: value is not None and value > reference,
        "lt": lambda: value is not None and value < reference,
    }
    if operator not in operations:
        raise ValueError(f"Unknown condition operator: {operator!r}")
    return bool(operations[operator]())


def compile_routes(raw: dict[str, Any], source_key: str) -> list[Route]:
    endpoints = {str(item.get("id")): item for item in raw.get("endpoints", [])}
    routes: list[Route] = []
    for route in raw.get("routes", []):
        if not route.get("enabled", True):
            continue
        sources = route.get("sources") or []
        if not route.get("match_all_sources", False) and not any(
            source.get("key") == source_key for source in sources
        ):
            continue
        targets: list[Target] = []
        for spec in route.get("targets") or []:
            endpoint = spec.get("endpoint") or {}
            endpoint = endpoints.get(str(endpoint.get("id")), endpoint)
            if not spec.get("enabled", True) or not endpoint.get("enabled", True):
                continue
            endpoint_type = str(endpoint.get("type") or "")
            if endpoint_type not in {"sms", "telegram", "messenger", "webhook", "reticulum"}:
                continue
            raw_id = endpoint.get("id")
            targets.append(
                Target(
                    endpoint_id=int(raw_id) if raw_id is not None else None,
                    endpoint_key=str(endpoint.get("key") or raw_id or ""),
                    endpoint_type=endpoint_type,
                    config=dict(endpoint.get("config") or {}),
                    transform=dict(spec.get("transform") or {}),
                    route_id=int(route["id"]) if route.get("id") else None,
                )
            )
        if targets:
            routes.append(
                Route(
                    name=str(route.get("name") or route.get("key") or "unnamed"),
                    condition=route.get("filter"),
                    targets=targets,
                )
            )
    return routes


class RouteDispatcher:
    def __init__(
        self,
        orchestrator_url: str,
        service_key: str,
        source_key: str,
        state: StateStore,
    ) -> None:
        self._base = orchestrator_url.rstrip("/")
        self._headers = {"X-Service-Key": service_key} if service_key else {}
        self._source_key = source_key
        self._state = state
        self._lock = threading.RLock()
        self._routes: list[Route] = []

    def reload(self) -> int:
        response = requests.get(
            f"{self._base}/api/telegram_relay/config",
            headers=self._headers,
            timeout=(5, 30),
        )
        response.raise_for_status()
        routes = compile_routes(response.json(), self._source_key)
        with self._lock:
            self._routes = routes
        logger.info("Loaded %d Reticulum source route(s)", len(routes))
        return len(routes)

    def dispatch(self, message: NormalizedMessage) -> None:
        with self._lock:
            routes = list(self._routes)
        for route in routes:
            if not matches_condition(route.condition, message):
                continue
            for target in route.targets:
                self._submit(message, target)
            logger.info("Route %r forwarded LXMF message %s", route.name, message.message_id)

    def _submit(self, message: NormalizedMessage, target: Target) -> None:
        message = message.redacted(target.transform.get("redact") or [])
        display = message.display_text()
        delivery: dict[str, Any]
        payload: dict[str, Any] = {"text": display}
        if target.endpoint_type == "sms":
            phone = str(target.config.get("phone") or "").strip()
            if not phone:
                raise ValueError(f"SMS endpoint {target.endpoint_key!r} has no phone")
            delivery = {
                "gateway_key": "sms-main",
                "address": {"phone": phone},
                "recovery_policy": target.config.get("recovery_policy", "digest_hold"),
            }
            payload = {"text": f"rns: {display}"}
        elif target.endpoint_type == "telegram":
            chat_id = target.config.get("chat_id")
            if chat_id is None:
                raise ValueError(f"Telegram endpoint {target.endpoint_key!r} has no chat_id")
            delivery = {
                "gateway_key": "telegram-main",
                "address": {"chat_id": int(chat_id)},
                "recovery_policy": target.config.get("recovery_policy", "replay"),
            }
        elif target.endpoint_type == "messenger":
            thread_id = str(target.config.get("thread_id") or "").strip()
            if not thread_id:
                raise ValueError(f"Messenger endpoint {target.endpoint_key!r} has no thread_id")
            delivery = {
                "gateway_key": "messenger-main",
                "address": {"thread_id": thread_id},
                "recovery_policy": target.config.get("recovery_policy", "replay"),
            }
        elif target.endpoint_type == "reticulum":
            destination_hash = str(target.config.get("destination_hash") or "").strip().lower()
            if not destination_hash:
                raise ValueError(f"Reticulum endpoint {target.endpoint_key!r} has no destination hash")
            delivery = {
                "gateway_key": "reticulum-main",
                "address": {
                    "destination_hash": destination_hash,
                    "delivery_method": target.config.get("delivery_method", "direct"),
                },
                "recovery_policy": target.config.get("recovery_policy", "replay"),
            }
        else:
            url = str(target.config.get("url") or "").strip()
            if not url:
                raise ValueError(f"Webhook endpoint {target.endpoint_key!r} has no URL")
            payload = {
                "message_id": message.message_id,
                "source_hash": message.source_hash,
                "destination_hash": message.destination_hash,
                "sender_name": message.sender_name,
                "text": message.text,
                "title": message.title,
                "timestamp": message.timestamp,
                "fields": message.fields,
            }
            delivery = {
                "gateway_key": "webhook-main",
                "address": {
                    "url": url,
                    "headers": target.config.get("headers") or {},
                    "timeout": target.config.get("timeout", 15),
                },
                "recovery_policy": target.config.get("recovery_policy", "replay"),
            }
        if target.endpoint_id is not None:
            delivery["target_endpoint_id"] = target.endpoint_id
        if target.route_id is not None:
            delivery["route_id"] = target.route_id
        delivery["idempotency_key"] = (
            f"reticulum:{message.message_id}:{target.endpoint_key}"
        )
        body = {
            "direction": "outbound",
            "kind": "text",
            "source_gateway_key": "reticulum-main",
            "external_id": message.message_id,
            "conversation_key": message.source_hash,
            "payload": payload,
            "metadata": {
                "source_type": "reticulum",
                "source_label": message.sender_name or message.source_hash[:12],
                "source_hash": message.source_hash,
                "title": message.title,
            },
            "idempotency_key": f"reticulum:{message.message_id}",
            "deliveries": [delivery],
        }
        response = requests.post(
            f"{self._base}/api/message-hub/messages",
            json=body,
            headers=self._headers,
            timeout=(5, 30),
        )
        response.raise_for_status()
        if target.endpoint_type == "sms":
            self._state.set_context(str(target.config["phone"]), message.source_hash)

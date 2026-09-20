from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


def compile_routes(
    raw: dict[str, Any], source_key: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compile connector-agnostic routes for one source connector.

    Returns raw target endpoint configurations and rule dictionaries. Keeping
    this step free of adapter and validation dependencies also makes route
    selection independently testable.
    """
    endpoints = raw.get("endpoints", [])
    endpoint_by_id = {str(endpoint.get("id")): endpoint for endpoint in endpoints}
    target_endpoints = [
        endpoint for endpoint in endpoints
        if "target" in (endpoint.get("capabilities") or [])
        and endpoint.get("type") in {"sms", "webhook"}
    ]
    active_target_ids = {
        str(endpoint.get("id")) for endpoint in target_endpoints
        if endpoint.get("enabled", True)
    }

    rules: list[dict[str, Any]] = []
    for route in raw.get("routes", []):
        sources = route.get("sources") or []
        source_matches = route.get("match_all_sources", False) or any(
            source.get("key") == source_key for source in sources
        )
        if not source_matches:
            continue

        actions: list[dict[str, Any]] = []
        for target in route.get("targets") or []:
            endpoint = target.get("endpoint") or {}
            endpoint_id = str(endpoint.get("id", ""))
            configured_endpoint = endpoint_by_id.get(endpoint_id, endpoint)
            if not target.get("enabled", True) or not configured_endpoint.get("enabled", True):
                continue
            if endpoint_id not in active_target_ids:
                logger.warning(
                    "Route '%s': target endpoint '%s' has no active adapter",
                    route.get("name", route.get("key", "unnamed")),
                    configured_endpoint.get("key", endpoint_id),
                )
                continue

            transform = target.get("transform") or {}
            action: dict[str, Any] = {
                "type": "forward",
                "destination": endpoint_id,
                "redact": transform.get("redact", []),
            }
            if transform.get("include_fields"):
                action["include_fields"] = transform["include_fields"]
            if transform.get("exclude_fields"):
                action["exclude_fields"] = transform["exclude_fields"]
            actions.append(action)

        rules.append({
            "name": route.get("name", route.get("key", "unnamed")),
            "priority": 100,
            "enabled": bool(route.get("enabled", True)),
            "continue": True,
            "conditions": route.get("filter"),
            "actions": actions,
        })

    return target_endpoints, rules

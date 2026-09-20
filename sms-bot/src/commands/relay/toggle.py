from __future__ import annotations

from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


def _resolve_route(target: str) -> dict | None:
    """Resolve a route by key, index, name, or the sole SMS route."""
    routes = _orchestrator.get_message_routes()
    if not routes:
        return None
    if not target:
        sms_routes = [
            route for route in routes
            if any(
                item.get("endpoint", {}).get("type") == "sms"
                for item in route.get("targets", [])
            )
        ]
        return sms_routes[0] if len(sms_routes) == 1 else None
    # Try 1-based numeric index
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(routes):
            return routes[idx]
    # Match by stable key or exact name, then by unambiguous prefix.
    target_lower = target.lower()
    for route in routes:
        if route.get("key", "").lower() == target_lower:
            return route
        if route.get("name", "").lower() == target_lower:
            return route
    matches = [
        route for route in routes
        if route.get("key", "").lower().startswith(target_lower)
        or route.get("name", "").lower().startswith(target_lower)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


class RelayStartCommand(BaseCommand):
    path = "relay/start"
    aliases = ["relay/enable", "relay/on"]
    description = "Enable a message route"
    usage = "relay on [route]"

    def execute(self, cmd: ParsedCommand) -> str:
        return _toggle(cmd, enabled=True)


class RelayStopCommand(BaseCommand):
    path = "relay/stop"
    aliases = ["relay/disable", "relay/off"]
    description = "Disable a message route"
    usage = "relay off [route]"

    def execute(self, cmd: ParsedCommand) -> str:
        return _toggle(cmd, enabled=False)


def _toggle(cmd: ParsedCommand, enabled: bool) -> str:
    target = " ".join(cmd.positional)
    route = _resolve_route(target)
    if route is None:
        detail = f"Route '{target}' not found" if target else "More than one route is available"
        return error_response(ERR_BAD_ARG, detail, "Use relay to see available routes")

    current = route.get("enabled", False)
    if current == enabled:
        return f"'{route['name']}' already {'on' if enabled else 'off'}"

    result = _orchestrator.set_message_route_enabled(route["key"], enabled)
    if result is None:
        return error_response(ERR_INTERNAL, "Failed to update message route")

    suffix = "" if result.get("runtime_applied", True) else " (saved; connector unavailable)"
    return f"'{route['name']}' {'on' if enabled else 'off'}{suffix}"

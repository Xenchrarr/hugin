from __future__ import annotations

from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.errors import ERR_BAD_ARG, ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


def _resolve_rule(target: str) -> dict | None:
    """Resolve a relay rule by 1-based index or (partial) name."""
    rules = _orchestrator.get_relay_rules()
    if not rules:
        return None
    # Try 1-based numeric index
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(rules):
            return rules[idx]
    # Match by exact name then prefix
    target_lower = target.lower()
    for rule in rules:
        if rule.get("name", "").lower() == target_lower:
            return rule
    for rule in rules:
        if rule.get("name", "").lower().startswith(target_lower):
            return rule
    return None


class RelayStartCommand(BaseCommand):
    path = "relay/start"
    aliases = ["relay/enable"]
    description = "Enable a Telegram relay rule"
    usage = "relay/start <num|name>"
    requires_pin = True

    def execute(self, cmd: ParsedCommand) -> str:
        return _toggle(cmd, enabled=True)


class RelayStopCommand(BaseCommand):
    path = "relay/stop"
    aliases = ["relay/disable"]
    description = "Disable a Telegram relay rule"
    usage = "relay/stop <num|name>"
    requires_pin = True

    def execute(self, cmd: ParsedCommand) -> str:
        return _toggle(cmd, enabled=False)


def _toggle(cmd: ParsedCommand, enabled: bool) -> str:
    if not cmd.positional:
        action = "start" if enabled else "stop"
        return error_response(ERR_BAD_ARG, f"Usage: relay/{action} <num|name>")

    target = " ".join(cmd.positional)
    rule = _resolve_rule(target)
    if rule is None:
        return error_response(ERR_BAD_ARG, f"Rule '{target}' not found",
                              "Use relay/list to see available rules")

    current = rule.get("enabled", False)
    if current == enabled:
        state = "already enabled" if enabled else "already disabled"
        return f"OK rule '{rule['name']}' is {state}"

    result = _orchestrator.set_relay_rule_enabled(rule["id"], enabled)
    if result is None:
        return error_response(ERR_INTERNAL, "Failed to update relay rule")

    state = "enabled" if enabled else "disabled"
    return f"OK rule '{rule['name']}' {state}"

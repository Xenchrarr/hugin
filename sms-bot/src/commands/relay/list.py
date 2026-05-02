from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class RelayListCommand(BaseCommand):
    path = "relay/list"
    aliases = ["relay/ls"]
    description = "List all Telegram relay rules with their enabled state"
    usage = "relay/list"

    def execute(self, cmd: ParsedCommand) -> str:
        rules = _orchestrator.get_relay_rules()
        if rules is None:
            return "ERR_INTERNAL: Could not fetch relay rules"
        if not rules:
            return "No relay rules configured."
        lines = []
        for i, rule in enumerate(rules, 1):
            state = "ON " if rule.get("enabled") else "OFF"
            name = rule.get("name", f"rule-{rule.get('id')}")
            prio = rule.get("priority", "?")
            lines.append(f"{i}. [{state}] {name} (prio {prio})")
        return "\n".join(lines)

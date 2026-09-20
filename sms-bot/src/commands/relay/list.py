from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class RelayListCommand(BaseCommand):
    path = "relay/list"
    aliases = ["relay/ls", "relay"]
    description = "Show message routes and their enabled targets"
    usage = "relay"

    def execute(self, cmd: ParsedCommand) -> str:
        routes = _orchestrator.get_message_routes()
        if routes is None:
            return "ERR_INTERNAL: Could not fetch message routes"
        if not routes:
            return "No message routes configured."
        lines = []
        for i, route in enumerate(routes, 1):
            state = "ON" if route.get("enabled") else "OFF"
            name = route.get("name", route.get("key", f"route-{route.get('id')}"))
            targets = []
            for target in route.get("targets", []):
                endpoint = target.get("endpoint", {})
                marker = "" if target.get("enabled", True) else " (off)"
                targets.append(f"{endpoint.get('name', endpoint.get('key', '?'))}{marker}")
            target_text = ", ".join(targets) or "no targets"
            lines.append(f"{i}. [{state}] {name} -> {target_text}")
        return "\n".join(lines)

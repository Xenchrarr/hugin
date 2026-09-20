import os

from src.api.core import HuginCoreClient
from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))
_orchestrator = OrchestratorClient()


class StatusCommand(BaseCommand):
    path = "status"
    aliases = ["home/status"]
    description = "Show compact home and service status"
    usage = "status"

    def execute(self, cmd: ParsedCommand) -> str:
        configured = cmd.user_config.get("status_entities", {})
        if isinstance(configured, list):
            labels = {entity: entity.rsplit(".", 1)[-1].replace("_", " ") for entity in configured}
        elif isinstance(configured, dict):
            labels = {str(entity): str(label) for label, entity in configured.items()}
        else:
            labels = {}

        parts: list[str] = []
        if labels:
            states = _core.get_home_states(list(labels))
            if states is not None:
                for state in states:
                    entity = state.get("entity_id", "")
                    value = state.get("state", "?")
                    unit = state.get("unit", "")
                    parts.append(f"{labels.get(entity, entity)} {value}{unit}")

        current = _core.get_today_energy()
        if current is not None:
            try:
                solar_kwh = round(float(current.get("total_energy_wh") or 0) / 1000, 1)
                parts.append(f"solar {solar_kwh}kWh")
            except (TypeError, ValueError):
                pass

        service_bits = []
        for key, label in (("database", "db"), ("hugin_core", "core"), ("telegram_bot", "tg")):
            state = _orchestrator.get_service_status(key)
            if state is not None:
                service_bits.append(f"{label}:{'ok' if state else 'down'}")
        if service_bits:
            parts.append(" ".join(service_bits))

        return "Status: " + ("; ".join(parts) if parts else "no status entities configured")

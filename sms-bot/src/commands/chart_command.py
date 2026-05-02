import os

from src.api.core import HuginCoreClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


class ChartCommand(BaseCommand):
    path = "chart"
    aliases = ["chart/today", "solar"]
    description = "Show today's solar production from Growatt and EcoFlow"
    usage = "chart"

    def execute(self, cmd: ParsedCommand) -> str:
        parts: list[str] = []

        growatt = _core.get_growatt_data()
        if growatt:
            current_w = growatt.get("currentPower", "N/A")
            total_kwh = growatt.get("todayEnergy", "N/A")
            parts.append(f"Growatt: {total_kwh} today (now {current_w})")
        else:
            parts.append("Growatt: unavailable")

        ecoflow = _core.get_today_energy()
        if ecoflow:
            total_wh = ecoflow.get("total_energy_wh", 0)
            pv1_wh = ecoflow.get("pv1_energy_wh", 0)
            pv2_wh = ecoflow.get("pv2_energy_wh", 0)
            total_kwh_e = round(total_wh / 1000.0, 2)
            parts.append(
                f"EcoFlow: {total_kwh_e} kWh today (PV1 {round(pv1_wh/1000,2)} kWh, PV2 {round(pv2_wh/1000,2)} kWh)"
            )
        else:
            parts.append("EcoFlow: unavailable")

        return " | ".join(parts)

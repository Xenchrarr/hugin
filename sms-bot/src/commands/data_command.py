import os

from src.api.core import HuginCoreClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


class DataCommand(BaseCommand):
    path = "data"
    aliases = ["inverter"]
    description = "Show current inverter power and today's total energy"
    usage = "data"

    def execute(self, cmd: ParsedCommand) -> str:
        growatt = _core.get_growatt_data()
        if not growatt:
            return "Inverter data unavailable"

        current_w = growatt.get("currentPower", "N/A")
        today_kwh = growatt.get("todayEnergy", "N/A")
        total_kwh = growatt.get("totalEnergy", "N/A")

        return f"Now: {current_w} W | Today: {today_kwh} kWh | Total: {total_kwh} kWh"

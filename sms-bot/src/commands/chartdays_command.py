import os
from datetime import datetime

from src.api.core import HuginCoreClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))

_MAX_DAYS = 30
_DEFAULT_DAYS = 7


class ChartDaysCommand(BaseCommand):
    path = "chartdays"
    aliases = []
    description = "Show energy production per day for the last N days"
    usage = "chartdays [days]"

    def execute(self, cmd: ParsedCommand) -> str:
        days = _DEFAULT_DAYS
        if cmd.positional:
            try:
                days = max(1, min(int(cmd.positional[0]), _MAX_DAYS))
            except ValueError:
                return f"Usage: {self.usage} — days must be a number"

        data = _core.get_daily_energy(days)
        if not data:
            return "Energy data unavailable"

        entries: list[dict] = data.get("days", [])
        if not entries:
            return "No energy data found"

        lines: list[str] = []
        for entry in entries:
            date_str = entry.get("date", "")
            try:
                label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %d %b")
            except ValueError:
                label = date_str
            total_kwh = round(entry.get("total_energy_wh", 0) / 1000, 2)
            lines.append(f"{label}: {total_kwh} kWh")

        return "\n".join(lines)

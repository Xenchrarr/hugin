import os

from src.api.core import HuginCoreClient
from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))
_orchestrator = OrchestratorClient()


class WeatherCommand(BaseCommand):
    path = "weather"
    aliases = ["weather/text"]
    description = "Show today's weather forecast as text"
    usage = "weather"

    def execute(self, cmd: ParsedCommand) -> str:
        user = _orchestrator.lookup_user(channel="sms", identifier=cmd.sender_phone or "")
        location_id = (user.get("config") or {}).get("weather_location_id", "") if user else ""
        if not location_id:
            return "No weather location configured for your account"

        summary = _core.get_weather_summary(location_id)
        if not summary:
            return "Weather data unavailable"

        return summary.get("text", "Weather data unavailable")

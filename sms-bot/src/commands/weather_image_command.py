import os

from src.api.core import HuginCoreClient
from src.commands.base_command import BaseCommand
from src.models.command_response import CommandResponse
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


class WeatherImageCommand(BaseCommand):
    path = "weather/image"
    aliases = ["weather/img"]
    description = "Send today's weather forecast as an MMS image"
    usage = "weather/image"

    def execute(self, cmd: ParsedCommand) -> str | CommandResponse:
        location_id = cmd.user_config.get("weather_location_id", "")
        if not location_id:
            return "No weather location configured for your account"

        image_bytes = _core.get_weather_image_bytes(location_id)
        if not image_bytes:
            return "Weather image unavailable"

        return CommandResponse(text="Weather forecast", image_bytes=image_bytes, image_mime="image/png")

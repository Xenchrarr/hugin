import os
from datetime import datetime

from src.api.core import HuginCoreClient
from src.api.printer import print_content, print_image
from src.commands.base_command import BaseCommand
from src.commands.today_command import format_today
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))
class PrintCommand(BaseCommand):
    path = "print"
    aliases = []
    description = "Print today, weather, shopping, or a note"
    usage = "print <today|weather|list|note TEXT>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "Usage: print today|weather|list|note TEXT"
        kind = cmd.positional[0].lower()

        if kind == "today":
            data = _core.get_today()
            if data is None:
                return "Today data unavailable"
            ok = print_content(format_today(data).splitlines(), title="TODAY")
        elif kind in ("list", "shopping"):
            content = _core.get_shopping_list()
            if content is None:
                return "Shopping list unavailable"
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            ok = bool(lines) and print_content(lines, title="SHOPPING")
        elif kind == "weather":
            location = cmd.user_config.get("weather_location_id", "")
            image = _core.get_weather_image_bytes(location) if location else None
            if not image:
                return "Weather image unavailable"
            ok = print_image(image)
        elif kind == "note":
            text = " ".join(cmd.positional[1:]).strip()
            if not text:
                return "Usage: print note <text>"
            ok = print_content([text], title="NOTE", footer=datetime.now().strftime("%d.%m %H:%M"))
        else:
            return "Usage: print today|weather|list|note TEXT"
        return "OK printed" if ok else "Print failed"

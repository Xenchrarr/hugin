from __future__ import annotations

import requests

from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand


class TransitCommand(BaseCommand):
    path = "bus"
    aliases = ["transit"]
    description = "Get a compact trip result from a configured transit webhook"
    usage = "bus <destination>"

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "Usage: bus <destination>"
        url = cmd.user_config.get("transit_url", "")
        if not url:
            return "No transit webhook configured. Set config.transit_url."
        destination = " ".join(cmd.positional)
        try:
            response = requests.get(
                url,
                params={"destination": destination, "user_id": cmd.user_id},
                timeout=(5, 20),
            )
            response.raise_for_status()
            if "application/json" in response.headers.get("content-type", ""):
                text = str(response.json().get("text", ""))
            else:
                text = response.text
            return text.strip() or "No departures found"
        except Exception:
            return "Transit lookup unavailable"

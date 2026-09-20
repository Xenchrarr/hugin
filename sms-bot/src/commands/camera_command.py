import os

from src.api.core import HuginCoreClient
from src.commands.base_command import BaseCommand
from src.models.command_response import CommandResponse
from src.models.parsed_command import ParsedCommand

_core = HuginCoreClient(os.environ.get("CORE_API_URL", "http://hugin-core:5100"))


class CameraCommand(BaseCommand):
    path = "cam"
    aliases = ["camera"]
    description = "Send the latest camera snapshot by MMS"
    usage = "cam"

    def execute(self, cmd: ParsedCommand) -> CommandResponse | str:
        image = _core.get_camera_snapshot()
        if not image:
            return "Camera unavailable"
        return CommandResponse(text="Latest camera snapshot", image_bytes=image, image_mime="image/jpeg")

from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.services.home_assistant_service import trigger_automation


class TriggerAutomation(BaseCommand):
    path = "home/dev"
    aliases = ["trigger/tv"]
    description = "Trigger a Home Assistant automation"
    usage = "home/dev <entity_id>"
    requires_pin = True

    def execute(self, cmd: ParsedCommand) -> str:
        if not cmd.positional:
            return "ERR_BAD_ARG: Missing entity_id. Hint: home/dev automation.watch_tv"
        entity_id = cmd.positional[0]
        trigger_automation(entity_id)
        return f"OK {entity_id} triggered"
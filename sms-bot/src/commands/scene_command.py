from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand
from src.services.home_assistant_service import trigger_automation


class SceneCommand(BaseCommand):
    path = "scene"
    aliases = ["mode"]
    description = "Run a named Home Assistant scene or automation"
    usage = "scene <name>"

    def execute(self, cmd: ParsedCommand) -> str:
        scenes = cmd.user_config.get("sms_scenes", {})
        if not isinstance(scenes, dict) or not scenes:
            return "No scenes configured. Set config.sms_scenes."
        if not cmd.positional or cmd.positional[0].lower() == "list":
            return "Scenes: " + ", ".join(sorted(str(name) for name in scenes))
        raw = " ".join(cmd.positional).lower()
        match = next(
            ((str(key), value) for key, value in sorted(scenes.items(), key=lambda item: len(str(item[0])), reverse=True)
             if raw == str(key).lower() or raw.startswith(str(key).lower() + " ")),
            None,
        )
        if not match:
            return f"Unknown scene '{raw}'. Try: scene list"
        display_name, definition = match
        extra = raw[len(display_name):].strip()
        variables = None
        if isinstance(definition, dict):
            entity = definition.get("entity_id") or definition.get("entity")
            if extra:
                variable_name = str(definition.get("argument_variable") or "duration")
                variables = {variable_name: extra}
        else:
            entity = definition
        if not entity:
            return f"Scene '{display_name}' has no entity_id"
        result = trigger_automation(str(entity), variables=variables)
        if result is None:
            return f"Could not run {display_name}"
        return f"OK {display_name}" + (f" ({extra})" if extra else "")

import logging
from typing import TYPE_CHECKING

from src.commands.base_command import BaseCommand
from src.models.errors import ERR_INTERNAL, error_response
from src.models.parsed_command import ParsedCommand
from src.services.ai_service import AIService, is_available

if TYPE_CHECKING:
    from src.command_resolver import CommandResolver

logger = logging.getLogger(__name__)


class AiCommand(BaseCommand):
    path = "ai"
    aliases = ["chat"]
    description = "Chat with AI assistant (or ask it to run a command for you)"
    usage = "ai <message>"

    def __init__(
        self,
        command_registry: dict[str, str] | None = None,
        resolver: "CommandResolver | None" = None,
    ) -> None:
        self._ai = AIService(command_registry=command_registry)
        self._resolver = resolver

    def execute(self, cmd: ParsedCommand) -> str:
        if not is_available():
            return "AI is not available. Contact admin to configure OPENAI_API_KEY."

        if not cmd.positional:
            return error_response("ERR_BAD_ARG", "Usage: ai <message>", self.usage)

        message = " ".join(cmd.positional)
        user_key = cmd.user_id or cmd.sender_phone or "anon"
        nlu = self._resolver is not None

        result = self._ai.chat(message, user_key=user_key, nlu=nlu)

        if result["type"] == "error":
            return error_response(ERR_INTERNAL, result["message"])

        if result["type"] == "command" and self._resolver is not None:
            path = result.get("path", "")
            args = result.get("args", [])
            logger.info("ai NLU mapped '%s' → %s %s", message, path, args)
            handler, _ = self._resolver.resolve(path)
            if handler is not None:
                cmd.path = path
                cmd.positional = args
                try:
                    return handler.execute(cmd)
                except Exception as e:
                    logger.exception("ai NLU dispatch to %s failed: %s", path, e)
                    return error_response(ERR_INTERNAL, "Command failed")

        return result.get("message", "")

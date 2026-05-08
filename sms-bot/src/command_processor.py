import logging

from src.api.orchestrator import OrchestratorClient
from src.command_resolver import CommandResolver
from src.commands.base_command import BaseCommand
from src.commands.help_command import HelpCommand
from src.commands.get_shoppinglist import GetShoppingListCommand
from src.commands.list_add import ListAddCommand
from src.commands.list_rm import ListRmCommand
from src.commands.get_ideas import GetIdeasCommand
from src.commands.ideas_add import IdeasAddCommand
from src.commands.remind_command import RemindCommand
from src.commands.remind_list_command import RemindListCommand
from src.commands.snooze_command import SnoozeCommand
from src.commands.dismiss_command import DismissCommand
from src.commands.trigger_automation import TriggerAutomation
from src.commands.chart_command import ChartCommand
from src.commands.tg.list import TgListCommand
from src.commands.tg.send import TgSendCommand
from src.commands.tg.reply import TgReplyCommand
from src.commands.relay.list import RelayListCommand
from src.commands.relay.toggle import RelayStartCommand, RelayStopCommand
from src.commands.relay.preset import RelayPresetOnCommand, RelayPresetOffCommand
from src.commands.agenda_command import AgendaCommand
from src.commands.ai_command import AiCommand
from src.models.errors import (
    ERR_AUTH,
    ERR_AMBIG,
    ERR_INTERNAL,
    ERR_PARSE,
    ERR_UNKNOWN_CMD,
    error_response,
)
from src.parser import parse
from src.services.ai_service import AIService, is_available as ai_available

logger = logging.getLogger(__name__)

_orchestrator = OrchestratorClient()


class CommandProcessor:
    def __init__(self):
        self.resolver = CommandResolver()

        non_ai_commands: list[BaseCommand] = [
            HelpCommand(),
            GetShoppingListCommand(),
            ListAddCommand(),
            ListRmCommand(),
            GetIdeasCommand(),
            IdeasAddCommand(),
            RemindCommand(),
            RemindListCommand(),
            SnoozeCommand(),
            DismissCommand(),
            TriggerAutomation(),
            ChartCommand(),
            TgListCommand(),
            TgSendCommand(),
            TgReplyCommand(),
            RelayListCommand(),
            RelayStartCommand(),
            RelayStopCommand(),
            RelayPresetOnCommand(),
            RelayPresetOffCommand(),
            AgendaCommand(),
        ]

        # Build command registry for NLU before AiCommand so it can be passed in
        self._command_registry: dict[str, str] = {
            cmd.path: cmd.description
            for cmd in non_ai_commands
        }

        ai_cmd = AiCommand(
            command_registry=self._command_registry,
            resolver=self.resolver,
        )
        # Include ai in the registry description for the NLU fallback prompt
        self._command_registry[ai_cmd.path] = ai_cmd.description

        commands: list[BaseCommand] = non_ai_commands + [ai_cmd]

        for cmd in commands:
            self.resolver.register(cmd.path, cmd)
            for alias in cmd.aliases:
                self.resolver.register(alias, cmd)

        # Give HelpCommand access to the resolver
        for cmd in commands:
            if isinstance(cmd, HelpCommand):
                cmd.set_resolver(self.resolver)

        self._ai = AIService(command_registry=self._command_registry)

    def process(self, text: str, sender: str = "") -> str:
        # Resolve user by phone number before processing any command
        user = _orchestrator.lookup_user(channel='sms', identifier=sender)
        if user is None:
            logger.warning("Unknown sender %s. Rejecting.", sender)
            return "Unknown user. Contact admin."

        try:
            cmd = parse(text)
        except ValueError:
            return error_response(ERR_PARSE, "Could not parse message", "help")

        cmd.user_id = user.get('id')
        cmd.sender_phone = sender

        handler, suggestions = self.resolver.resolve(cmd.path)

        # Fallback: try path/first_positional for backward-compat space syntax
        # e.g. "get shoppinglist" → path="get", positional=["shoppinglist"] → try "get/shoppinglist"
        if handler is None and cmd.positional:
            compound = f"{cmd.path}/{cmd.positional[0].lower()}"
            fallback_handler, fallback_suggestions = self.resolver.resolve(compound)
            if fallback_handler is not None:
                handler = fallback_handler
                cmd.positional = cmd.positional[1:]
                suggestions = []

        if handler is None:
            if suggestions:
                return error_response(
                    ERR_AMBIG,
                    f"Ambiguous command: {cmd.path}",
                    f"Did you mean: {', '.join(suggestions)}?",
                )
            # NLU fallback: let AI interpret unrecognised input
            if ai_available():
                user_key = cmd.user_id or sender or "anon"
                ai_result = self._ai.chat(text, user_key=user_key, nlu=True)
                if ai_result["type"] == "command":
                    path = ai_result.get("path", "")
                    args = ai_result.get("args", [])
                    logger.info("NLU mapped '%s' → %s %s", text, path, args)
                    nlu_handler, _ = self.resolver.resolve(path)
                    if nlu_handler is not None:
                        cmd.path = path
                        cmd.positional = args
                        handler = nlu_handler
                    # Fall through to permission check below
                elif ai_result["type"] == "chat":
                    return ai_result.get("message", "")
            if handler is None:
                return error_response(ERR_UNKNOWN_CMD, f"Unknown command: {cmd.path}", "help")

        # Permission check: admins bypass; non-admins must have the command explicitly allowed
        if not user.get('is_admin'):
            allowed = user.get('allowed_commands')
            if allowed is None or handler.path not in allowed:
                return error_response(ERR_AUTH, "Permission denied", handler.path)

        try:
            return handler.execute(cmd)
        except Exception as e:
            logger.exception("Command %s failed: %s", cmd.path, e)
            return error_response(ERR_INTERNAL, "Command failed")


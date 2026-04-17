import logging

from src.auth import validate_pin
from src.command_resolver import CommandResolver
from src.commands.base_command import BaseCommand
from src.commands.help_command import HelpCommand
from src.commands.get_shoppinglist import GetShoppingListCommand
from src.commands.list_add import ListAddCommand
from src.commands.list_rm import ListRmCommand
from src.commands.remind_command import RemindCommand
from src.commands.remind_list_command import RemindListCommand
from src.commands.snooze_command import SnoozeCommand
from src.commands.dismiss_command import DismissCommand
from src.commands.trigger_automation import TriggerAutomation
from src.models.errors import (
    ERR_AUTH,
    ERR_AMBIG,
    ERR_INTERNAL,
    ERR_PARSE,
    ERR_UNKNOWN_CMD,
    error_response,
)
from src.parser import parse

logger = logging.getLogger(__name__)


class CommandProcessor:
    def __init__(self):
        self.resolver = CommandResolver()

        commands: list[BaseCommand] = [
            HelpCommand(),
            GetShoppingListCommand(),
            ListAddCommand(),
            ListRmCommand(),
            RemindCommand(),
            RemindListCommand(),
            SnoozeCommand(),
            DismissCommand(),
            TriggerAutomation(),
        ]

        for cmd in commands:
            self.resolver.register(cmd.path, cmd)
            for alias in cmd.aliases:
                self.resolver.register(alias, cmd)

        # Give HelpCommand access to the resolver
        for cmd in commands:
            if isinstance(cmd, HelpCommand):
                cmd.set_resolver(self.resolver)

    def process(self, text: str, sender: str = "") -> str:
        try:
            cmd = parse(text)
        except ValueError:
            return error_response(ERR_PARSE, "Could not parse message", "help")

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
            return error_response(ERR_UNKNOWN_CMD, f"Unknown command: {cmd.path}", "help")

        if handler.requires_pin and not validate_pin(sender, cmd.pin):
            return error_response(ERR_AUTH, "PIN required", f"{handler.usage} #PIN")

        try:
            return handler.execute(cmd)
        except Exception as e:
            logger.exception("Command %s failed: %s", cmd.path, e)
            return error_response(ERR_INTERNAL, "Command failed")

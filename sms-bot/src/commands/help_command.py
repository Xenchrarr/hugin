from __future__ import annotations

from typing import TYPE_CHECKING

from src.commands.base_command import BaseCommand

if TYPE_CHECKING:
    from src.command_resolver import CommandResolver
    from src.models.parsed_command import ParsedCommand


class HelpCommand(BaseCommand):
    path = "help"
    aliases = ["?"]
    description = "Show available commands"
    usage = "help [command]"

    def __init__(self) -> None:
        self._resolver: CommandResolver | None = None

    def set_resolver(self, resolver: CommandResolver) -> None:
        self._resolver = resolver

    def execute(self, cmd: ParsedCommand) -> str:
        if not self._resolver:
            return "commands: (help unavailable)"

        commands = self._resolver.commands
        # Deduplicate: only show primary paths (skip aliases)
        seen_handlers: set[int] = set()
        primary: list[BaseCommand] = []
        for handler in commands.values():
            hid = id(handler)
            if hid not in seen_handlers:
                seen_handlers.add(hid)
                primary.append(handler)

        if cmd.positional:
            query = cmd.positional[0].lower()
            # Exact path help
            if query in commands:
                h = commands[query]
                aliases = f" (aliases: {', '.join(h.aliases)})" if h.aliases else ""
                return f"{h.path}: {h.usage} — {h.description}{aliases}"
            # Show all subcommands of a namespace
            matches = sorted(
                [h for h in primary if h.path.startswith(query + "/") or h.path == query],
                key=lambda h: h.path,
            )
            if matches:
                lines = [f"{h.path}: {h.usage} — {h.description}" for h in matches]
                return "; ".join(lines)
            return f"No help for '{query}'. Try: help"

        standalone = sorted(h.path for h in primary if "/" not in h.path)
        namespaces = sorted({h.path.split("/")[0] for h in primary if "/" in h.path})
        return f"cmds: {', '.join(standalone)} | groups: {', '.join(namespaces)} | try: help <group>"

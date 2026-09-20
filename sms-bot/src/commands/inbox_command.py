from __future__ import annotations

from src.api.orchestrator import OrchestratorClient
from src.commands.base_command import BaseCommand
from src.models.command_response import CommandResponse
from src.models.parsed_command import ParsedCommand

_orchestrator = OrchestratorClient()


class InboxCommand(BaseCommand):
    path = "inbox"
    aliases = ["messages"]
    description = "Show or retrieve messages stored during an SMS outage"
    usage = "inbox [sources|telegram [group]|reminders|system|next]"

    def execute(self, cmd: ParsedCommand) -> str | CommandResponse:
        if not cmd.sender_phone:
            return "ERR_INTERNAL: Missing sender phone"

        args = [arg.strip() for arg in cmd.positional if arg.strip()]
        if not args:
            return self._summary(cmd.sender_phone)
        action = args[0].lower()
        if action == "sources":
            return self._sources(cmd.sender_phone)

        source_type = None
        source_label = None
        if action in ("telegram", "tg"):
            source_type = "telegram"
            source_label = " ".join(args[1:]) or None
        elif action in ("reminder", "reminders", "rem"):
            source_type = "reminder"
        elif action == "system":
            source_type = "system"
        elif action != "next":
            return "Usage: inbox [sources|telegram [group]|reminders|system|next]"

        prepared = _orchestrator.prepare_message_hub_inbox(
            phone=cmd.sender_phone,
            source_type=source_type,
            source_label=source_label,
            limit=5,
        )
        if prepared is None:
            return "ERR_INTERNAL: Could not fetch waiting messages"
        delivery_ids = [int(item) for item in prepared.get("delivery_ids", [])]
        return CommandResponse(
            text=prepared.get("message", "No waiting messages."),
            ack_hub_delivery_ids=delivery_ids,
        )

    def _summary(self, phone: str) -> str:
        summary = _orchestrator.get_message_hub_inbox_summary(phone)
        if summary is None:
            return "ERR_INTERNAL: Could not fetch inbox summary"
        total = int(summary.get("total", 0))
        if not total:
            return "No waiting messages."
        by_type: dict[str, int] = {}
        for item in summary.get("sources", []):
            source_type = item.get("source_type", "other")
            by_type[source_type] = by_type.get(source_type, 0) + int(item.get("count", 0))
        counts = ", ".join(f"{key} {value}" for key, value in sorted(by_type.items()))
        return f"{total} messages waiting: {counts}. Try inbox sources."

    def _sources(self, phone: str) -> str:
        summary = _orchestrator.get_message_hub_inbox_summary(phone)
        if summary is None:
            return "ERR_INTERNAL: Could not fetch inbox sources"
        sources = summary.get("sources", [])
        if not sources:
            return "No waiting messages."
        return "Sources: " + "; ".join(
            f"{item.get('source_label', item.get('source_type'))} {item.get('count', 0)}"
            for item in sources[:10]
        )

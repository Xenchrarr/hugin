from __future__ import annotations

import re
from dataclasses import dataclass

from src.api.orchestrator import OrchestratorClient
from src.api.telegram_relay import TelegramRelayClient


_REFERENCE = re.compile(r"^\s*#(?P<reference>\d+)(?:(?:[ \t]+|\r?\n)(?P<body>[\s\S]*))?$", re.ASCII)
_ALIAS = re.compile(
    r"^\s*(?P<alias>[a-z][a-z0-9_-]{0,9}/[a-z0-9][a-z0-9_-]{0,17})"
    r"(?:(?:[ \t]+|\r?\n)(?P<body>[\s\S]*))?$",
    re.IGNORECASE | re.ASCII,
)
_LEGACY_TG_ALIASES = {"tg/list", "tg/convos", "tg/send", "tg/use", "tg/target", "tg/reply", "tg/r"}


@dataclass(frozen=True)
class RoutingInput:
    kind: str
    selector: str | int | None = None
    body: str = ""
    argument: str = ""


def parse_routing_input(text: str) -> RoutingInput | None:
    """Parse explicit hub syntax while retaining the message body verbatim."""
    stripped = text.strip()
    lowered = stripped.lower()
    if lowered == "/help":
        return RoutingInput("help")
    if lowered == "/chats" or lowered.startswith("/chats "):
        return RoutingInput("chats", argument=stripped[6:].strip())
    if lowered == "/history" or lowered.startswith("/history "):
        return RoutingInput("history", argument=stripped[8:].strip())

    match = _REFERENCE.fullmatch(text)
    if match:
        return RoutingInput(
            "route", int(match.group("reference")), match.group("body") or "", "reference"
        )
    match = _ALIAS.fullmatch(text)
    if match and match.group("alias").lower() not in _LEGACY_TG_ALIASES:
        return RoutingInput(
            "route", match.group("alias").lower(), match.group("body") or "", "alias"
        )
    return None


class ConversationRouter:
    def __init__(
        self, orchestrator: OrchestratorClient | None = None,
        telegram: TelegramRelayClient | None = None,
    ):
        self.orchestrator = orchestrator or OrchestratorClient()
        self.telegram = telegram or TelegramRelayClient()

    def handle(
        self, parsed: RoutingInput, *, user_id: int, event_id: str | None = None
    ) -> str:
        if parsed.kind == "help":
            return (
                "(hub) Reply: #184 Yes\n"
                "New: tg/nikolai Hello\n"
                "Lists: /chats, /history tg/nikolai"
            )
        if parsed.kind == "chats":
            try:
                page = max(int(parsed.argument or "1"), 1)
            except ValueError:
                return "(hub) Usage: /chats <page>"
            data = self.orchestrator.routing_chats(user_id, offset=(page - 1) * 10)
            if data is None:
                return "(hub) Conversation list is unavailable. Try again later."
            chats = data.get("chats") or []
            if not chats:
                return "(hub) No conversations are configured."
            lines = [f"{item['alias']} - {item['display_name']}" for item in chats]
            if data.get("more"):
                lines.append(f"More: /chats {page + 1}")
            return "(hub) Chats\n" + "\n".join(lines)
        if parsed.kind == "history":
            parts = parsed.argument.split()
            if not parts:
                return "(hub) Usage: /history tg/nikolai <before-ref>"
            before = None
            if len(parts) > 1:
                try:
                    before = int(parts[1].lstrip("#"))
                except ValueError:
                    return "(hub) History cursor must be a reference number."
            data = self.orchestrator.routing_history(user_id, parts[0].lower(), before)
            if data is None:
                return f"(hub) Unknown conversation or history unavailable: {parts[0]}"
            lines = []
            for item in data.get("messages") or []:
                arrow = "IN" if item["direction"] == "inbound" else "OUT"
                author = f" {item['author']}:" if item.get("author") else ""
                status = f" ({item['status']})" if arrow == "OUT" else ""
                lines.append(f"{arrow} #{item['reference']}{author} {item['body']}{status}")
            if data.get("more"):
                lines.append(f"More: /history {data['alias']} {data['before_reference']}")
            return f"(hub) History {data['alias']}\n" + ("\n".join(lines) or "No messages.")

        if not parsed.body.strip():
            target = f"#{parsed.selector}" if parsed.argument == "reference" else parsed.selector
            return f"(hub) Message body is empty. Example: {target} Hello"
        route = self.orchestrator.prepare_routed_message(
            user_id=user_id, selector_type=parsed.argument,
            selector=parsed.selector, body=parsed.body, event_id=event_id,
        )
        if route is None:
            target = f"#{parsed.selector}" if parsed.argument == "reference" else parsed.selector
            return f"(hub) Unknown or unavailable destination: {target}. Use /chats."
        if route.get("duplicate"):
            status = route.get("status")
            if status in {"accepted", "queued"}:
                verb = "Sent" if status == "accepted" else "Queued"
                return f"(hub) {verb} to {route['alias']}."
            return "(hub) This SMS was already processed; it was not sent again."
        if not route.get("available", True):
            self.orchestrator.update_routed_status(user_id, route["reference"], "failed", "integration unavailable")
            return f"(hub) {route['alias']} is unavailable. Try again later."
        if route.get("service") != "tg":
            self.orchestrator.update_routed_status(user_id, route["reference"], "failed", "integration adapter unavailable")
            return f"(hub) Integration '{route.get('service')}' is unavailable."

        result = self.telegram.send_routed_message(
            int(route["external_chat_id"]), route["body"],
            reply_to_message_id=route.get("reply_to_external_message_id"),
        )
        self.orchestrator.update_routed_status(
            user_id, route["reference"], result.status, result.detail,
            result.external_message_id,
        )
        if result.status == "accepted":
            return f"(hub) Sent to {route['alias']}."
        if result.status == "queued":
            return f"(hub) Queued for {route['alias']}."
        if result.status == "uncertain":
            return f"(hub) Send to {route['alias']} is uncertain; it will not be retried automatically."
        return f"(hub) Could not send to {route['alias']}: {result.detail or 'integration failure'}."


AMBIGUOUS_RESPONSE = (
    "(hub) Specify a conversation or reply reference.\n"
    "Example: #184 Yes\n"
    "Use /chats to list conversations."
)

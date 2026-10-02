import logging

from src.api.orchestrator import OrchestratorClient
from src.command_resolver import CommandResolver
from src.commands.base_command import BaseCommand
from src.commands.help_command import HelpCommand
from src.commands.get_shoppinglist import GetShoppingListCommand
from src.commands.list_add import ListAddCommand
from src.commands.list_rm import ListRmCommand
from src.commands.list_print import ListPrintCommand
from src.commands.get_ideas import GetIdeasCommand
from src.commands.ideas_add import IdeasAddCommand
from src.commands.remind_command import RemindCommand
from src.commands.remind_list_command import RemindListCommand
from src.commands.snooze_command import SnoozeCommand
from src.commands.dismiss_command import DismissCommand
from src.commands.trigger_automation import TriggerAutomation
from src.commands.chart_command import ChartCommand
from src.commands.data_command import DataCommand
from src.commands.weather_command import WeatherCommand
from src.commands.weather_image_command import WeatherImageCommand
from src.commands.chartdays_command import ChartDaysCommand
from src.commands.tg.list import TgListCommand
from src.commands.tg.send import TgSendCommand
from src.commands.tg.reply import TgReplyCommand
from src.commands.tg.use import TgUseCommand
from src.commands.fb.list import FbListCommand
from src.commands.fb.send import FbSendCommand
from src.commands.fb.reply import FbReplyCommand
from src.commands.fb.use import FbUseCommand
from src.commands.rns.list import RnsListCommand
from src.commands.rns.send import RnsSendCommand
from src.commands.rns.reply import RnsReplyCommand
from src.commands.rns.use import RnsUseCommand
from src.commands.relay.list import RelayListCommand
from src.commands.relay.toggle import RelayStartCommand, RelayStopCommand
from src.commands.relay.preset import RelayPresetOnCommand, RelayPresetOffCommand
from src.commands.agenda_command import AgendaCommand
from src.commands.ai_command import AiCommand
from src.commands.inbox_command import InboxCommand
from src.commands.menu_command import MenuCommand
from src.commands.today_command import TodayCommand
from src.commands.camera_command import CameraCommand
from src.commands.status_command import StatusCommand
from src.commands.scene_command import SceneCommand
from src.commands.print_command import PrintCommand
from src.commands.news_command import NewsCommand
from src.commands.transit_command import TransitCommand
from src.commands.run_command import RunCommand
from src.commands.brief_command import BriefCommand
from src.commands.quiet_command import QuietCommand
from src.commands.checkin_command import CheckinCommand, CheckinOkCommand
from src.commands.alarm_command import AlarmCommand, CallMeCommand
from src.models.errors import (
    ERR_AUTH,
    ERR_INTERNAL,
    ERR_PARSE,
    error_response,
)
from src.models.media_relay_result import MediaRelayResult
from src.parser import parse
from src.services.ai_service import AIService
from src.services.dumbphone_session import sessions
from src.conversation_routing import (
    AMBIGUOUS_RESPONSE,
    ConversationRouter,
    parse_routing_input,
)
from src.phone import normalize_phone

logger = logging.getLogger(__name__)

_orchestrator = OrchestratorClient()


class CommandProcessor:
    def __init__(self):
        self.resolver = CommandResolver()
        self._conversation_router = ConversationRouter(orchestrator=_orchestrator)

        non_ai_commands: list[BaseCommand] = [
            HelpCommand(),
            GetShoppingListCommand(),
            ListAddCommand(),
            ListRmCommand(),
            ListPrintCommand(),
            GetIdeasCommand(),
            IdeasAddCommand(),
            RemindCommand(),
            RemindListCommand(),
            SnoozeCommand(),
            DismissCommand(),
            TriggerAutomation(),
            ChartCommand(),
            DataCommand(),
            WeatherCommand(),
            WeatherImageCommand(),
            ChartDaysCommand(),
            TgListCommand(),
            TgSendCommand(),
            TgReplyCommand(),
            TgUseCommand(),
            FbListCommand(),
            FbSendCommand(),
            FbReplyCommand(),
            FbUseCommand(),
            RnsListCommand(),
            RnsSendCommand(),
            RnsReplyCommand(),
            RnsUseCommand(),
            RelayListCommand(),
            RelayStartCommand(),
            RelayStopCommand(),
            RelayPresetOnCommand(),
            RelayPresetOffCommand(),
            AgendaCommand(),
            InboxCommand(),
            MenuCommand(),
            TodayCommand(),
            CameraCommand(),
            StatusCommand(),
            SceneCommand(),
            PrintCommand(),
            NewsCommand(),
            TransitCommand(),
            RunCommand(),
            BriefCommand(),
            QuietCommand(),
            CheckinCommand(),
            CheckinOkCommand(),
            AlarmCommand(),
            CallMeCommand(),
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

    def acknowledge_hub_inbox(self, phone: str, delivery_ids: list[int]) -> bool:
        return _orchestrator.acknowledge_message_hub_inbox(phone, delivery_ids)

    def queue_sms_response(
        self,
        phone: str,
        message: str,
        idempotency_key: str,
        *,
        source_type: str = "sms-command",
        source_label: str = "SMS command",
        acknowledge_delivery_ids: list[int] | None = None,
    ) -> bool:
        return _orchestrator.queue_sms_response(
            phone,
            message,
            idempotency_key,
            source_type=source_type,
            source_label=source_label,
            acknowledge_delivery_ids=acknowledge_delivery_ids,
        ) is not None

    def queue_mms_response(
        self,
        phone: str,
        message: str,
        image_bytes: bytes,
        image_mime: str,
        idempotency_key: str,
        *,
        source_type: str = "sms-command",
        source_label: str = "SMS command",
        acknowledge_delivery_ids: list[int] | None = None,
    ) -> bool:
        return _orchestrator.queue_mms_response(
            phone,
            message,
            image_bytes,
            image_mime,
            idempotency_key,
            source_type=source_type,
            source_label=source_label,
            acknowledge_delivery_ids=acknowledge_delivery_ids,
        ) is not None

    def process_missed_call(self, sender: str):
        sender = normalize_phone(sender)
        user = _orchestrator.lookup_user(channel="sms", identifier=sender)
        if user is None:
            return None
        command = str((user.get("config") or {}).get("missed_call_command") or "").strip()
        if not command:
            return None
        logger.info("Running missed-call command for %s: %s", sender, command)
        return self.process(command, sender=sender)

    def process_media(
        self,
        caption: str,
        sender: str,
        image_bytes: bytes,
        image_mime: str,
    ) -> MediaRelayResult:
        """Route an inbound MMS image to an explicit or sticky Telegram target."""
        sender = normalize_phone(sender)
        user = _orchestrator.lookup_user(channel="sms", identifier=sender)
        if user is None:
            logger.warning("Unknown MMS sender %s. Rejecting.", sender)
            return MediaRelayResult(handled=True, response="Unknown user. Contact admin.")

        from src.api.telegram_relay import TelegramRelayClient
        from src.commands.tg.send import TgSendCommand

        relay = TelegramRelayClient()
        text = caption.strip()
        tokens = text.split()
        command = tokens[0].lower() if tokens else ""
        chat_id: int | None = None
        title = ""
        outgoing_caption = text

        if command in {"tg/send", "tg/use", "tg/target"}:
            if len(tokens) < 2:
                return MediaRelayResult(
                    handled=True,
                    response="ERR_BAD_ARG: MMS needs a Telegram target. Try tg/use <num> first.",
                )
            resolved = TgSendCommand._resolve_chat(tokens[1])
            if resolved is None:
                return MediaRelayResult(
                    handled=True,
                    response=f"ERR_BAD_ARG: Could not resolve conversation '{tokens[1]}'.",
                )
            chat_id, title = resolved
            outgoing_caption = " ".join(tokens[2:])
            relay.set_context(sender, chat_id)
        elif command in {"tg/reply", "tg/r", "reply", "r"}:
            outgoing_caption = " ".join(tokens[1:])

        if chat_id is None:
            context = relay.get_context(sender)
            if context is None:
                return MediaRelayResult(
                    handled=True,
                    response="No Telegram target. Send tg/use <num> first.",
                )
            chat_id = int(context["chat_id"])
            title = context.get("title") or str(chat_id)

        if not relay.send_media(chat_id, image_bytes, image_mime, outgoing_caption):
            return MediaRelayResult(handled=False)
        return MediaRelayResult(handled=True, response=f"OK photo sent to {title}")

    def process(
        self, text: str, sender: str = "", event_id: str | None = None
    ) -> str | None:
        sender = normalize_phone(sender)
        # Resolve user by phone number before processing any command
        user = _orchestrator.lookup_user(channel='sms', identifier=sender)
        if user is None:
            logger.warning("Unknown sender %s. Rejecting.", sender)
            # Silent rejection prevents reply loops and does not disclose hub data.
            return None

        routing_input = parse_routing_input(text)
        if routing_input is not None:
            return self._conversation_router.handle(
                routing_input, user_id=int(user["id"]), event_id=event_id
            )

        stripped = text.strip()
        control = stripped.lower()
        if control in ("more", "next"):
            return sessions.move(sender, 1)
        if control in ("back", "prev", "previous"):
            return sessions.move(sender, -1)
        if control == "cancel":
            return sessions.cancel(sender)
        if control in ("again", "repeat"):
            previous = sessions.last_command(sender)
            if not previous:
                return "Nothing to repeat."
            text = previous
        else:
            shortcuts = {
                "1": "today",
                "2": "list show",
                "3": "status",
                "4": "inbox",
                "5": "ideas show",
                "6": "help",
            }
            configured = (user.get("config") or {}).get("sms_shortcuts", {})
            if isinstance(configured, dict):
                shortcuts.update({str(k).lower(): str(v) for k, v in configured.items()})
            text = shortcuts.get(control, text)
            first_word = control.split(None, 1)[0] if control else ""
            scenes = (user.get("config") or {}).get("sms_scenes", {})
            if text == stripped and isinstance(scenes, dict):
                if any(str(name).lower() == first_word for name in scenes):
                    text = f"scene {stripped}"
            sessions.remember_command(sender, stripped)

        try:
            cmd = parse(text)
        except ValueError:
            return error_response(ERR_PARSE, "Could not parse message", "help")

        cmd.user_id = user.get('id')
        cmd.sender_phone = sender
        cmd.user_config = user.get("config") or {}

        handler, suggestions = self.resolver.resolve(cmd.path)

        # `relay` is both a useful status command and a command namespace.
        # Prefer a concrete subcommand when one is present so permission checks
        # apply to relay/start or relay/stop rather than the read-only list command.
        if cmd.path == "relay" and cmd.positional:
            compound = f"relay/{cmd.positional[0].lower()}"
            compound_handler, _ = self.resolver.resolve(compound)
            if compound_handler is not None:
                handler = compound_handler
                cmd.positional = cmd.positional[1:]
                suggestions = []

        # Fallback: consume space-separated namespace tokens as slash paths.
        # e.g. "relay preset on" -> "relay/preset/on".
        if handler is None and cmd.positional:
            for consumed in range(len(cmd.positional), 0, -1):
                compound = "/".join([cmd.path] + [part.lower() for part in cmd.positional[:consumed]])
                fallback_handler, _ = self.resolver.resolve(compound)
                if fallback_handler is not None:
                    handler = fallback_handler
                    cmd.positional = cmd.positional[consumed:]
                    suggestions = []
                    break

        if handler is None:
            # Never infer a destination for an unaddressed conversational reply.
            # AI remains available explicitly through the registered `ai` command.
            return AMBIGUOUS_RESPONSE

        # Permission check: admins bypass; non-admins must have the command explicitly allowed
        if not user.get('is_admin'):
            allowed = user.get('allowed_commands')
            if allowed is None or handler.path not in allowed:
                return error_response(ERR_AUTH, "Permission denied", handler.path)

        try:
            result = handler.execute(cmd)
            if isinstance(result, str) and len(result) > 160:
                return sessions.first_page(sender, result)
            return result
        except Exception as e:
            logger.exception("Command %s failed: %s", cmd.path, e)
            return error_response(ERR_INTERNAL, "Command failed")

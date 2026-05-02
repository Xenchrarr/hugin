import asyncio
import json
import logging
import os
import threading
from typing import Optional

from telegram.client import Telegram

from app.config import TelegramConfig
from app.destinations.base import AbstractDestination
from app.destinations.sms import SmsAdapter
from app.normalizer import MessageNormalizer, NormalizedMessage
from app.redactor import Redactor
from app.rules.engine import RuleEngine
from app.rules.models import ForwardAction, LogAction, SkipAction, Rule

logger = logging.getLogger(__name__)

_RECENT_CHATS_MAX = 20
_CACHE_PATH = "./data/tdlib/recent_chats.json"
_TITLE_MAX = 15
_CONVERSATIONS_LIMIT = 10


class TelegramForwarder:
    def __init__(
        self,
        telegram_config: TelegramConfig,
        rule_engine: RuleEngine,
        destinations: dict[str, AbstractDestination],
    ) -> None:
        self._telegram_config = telegram_config
        self._engine = rule_engine
        self._destinations = destinations
        self._normalizer = MessageNormalizer()
        self._redactor = Redactor()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # conversation tracker: chat_id → {chat_id, title, last_sender, last_text, timestamp}
        self._recent_chats: dict[int, dict] = {}
        # channel chat_ids to exclude from the conversations list
        self._channel_ids: set[int] = set()
        # reply context: sms phone number → chat_id of last forwarded message
        self._reply_context: dict[str, int] = {}
        self._cache_path = _CACHE_PATH
        self._load_cache()

        tg = telegram_config
        self._client = Telegram(
            api_id=tg.api_id,
            api_hash=tg.api_hash,
            phone=tg.phone_number,
            database_encryption_key=tg.db_encryption_key,
            files_directory="./data/tdlib",
        )

    def reload_config(
        self,
        destinations: dict[str, AbstractDestination],
        rules: list[Rule],
    ) -> None:
        """Hot-swap destinations and rule engine without restarting the Telegram client."""
        new_engine = RuleEngine(rules)
        with self._lock:
            old_destinations = self._destinations
            self._destinations = destinations
            self._engine = new_engine
        logger.info(
            "Config reloaded: %d destination(s), %d rule(s)",
            len(destinations), len(rules),
        )
        # Close old adapters that are no longer in the new set (fire-and-forget via main loop)
        loop = getattr(self, "_loop", None)
        for dest_id, adapter in old_destinations.items():
            if dest_id not in destinations:
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(adapter.aclose(), loop)
                else:
                    logger.debug("Cannot close old adapter '%s': no running loop", dest_id)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        loop = self._loop

        def _sync_handler(update: dict) -> None:
            asyncio.run_coroutine_threadsafe(self._handle_message(update), loop)

        self._client.login()
        self._seed_from_history()
        self._client.add_message_handler(_sync_handler)
        logger.info("Telegram forwarder running")
        while True:
            await asyncio.sleep(3600)

    async def _handle_message(self, update: dict) -> None:
        with self._lock:
            engine = self._engine
            destinations = self._destinations
        msg = self._normalizer.normalize(update)
        if msg is None:
            return

        self._update_recent_chat(msg)

        rules = engine.match(msg)
        if not rules:
            logger.debug(
                "No rules matched message %d in chat %d", msg.message_id, msg.chat_id
            )
            return

        for rule in rules:
            for action in rule.actions:
                await self._dispatch(action, msg, rule.name, destinations)

    async def _dispatch(
        self, action, msg: NormalizedMessage, rule_name: str, destinations: dict[str, AbstractDestination]
    ) -> None:
        if isinstance(action, SkipAction):
            logger.debug(
                "Rule '%s': skipping message %d in chat %d",
                rule_name, msg.message_id, msg.chat_id,
            )
            return

        if isinstance(action, LogAction):
            log_fn = getattr(logger, action.level, logger.info)
            log_fn(
                "Rule '%s' matched: message %d | chat_id=%d chat_type=%s chat_title=%r | sender_id=%s sender_name=%r | content=%s",
                rule_name,
                msg.message_id,
                msg.chat_id,
                msg.chat_type,
                msg.chat_title,
                msg.sender_id,
                msg.sender_name,
                msg.media_type or "text",
            )
            return

        if isinstance(action, ForwardAction):
            destination = destinations.get(action.destination)
            if destination is None:
                logger.error(
                    "Rule '%s': destination '%s' is not configured",
                    rule_name, action.destination,
                )
                return

            redacted = self._redactor.apply(msg, action.redact)
            payload = redacted.to_payload(
                include_fields=action.include_fields,
                exclude_fields=action.exclude_fields,
            )
            # For SMS destinations, always include context fields for message formatting
            # regardless of include_fields/exclude_fields on the action
            if isinstance(destination, SmsAdapter):
                payload.setdefault("chat_title", msg.chat_title)
                payload.setdefault("sender_name", msg.sender_name)
            logger.info(
                "Rule '%s': forwarding message %d → '%s'",
                rule_name, msg.message_id, action.destination,
            )
            await destination.send(payload)
            # Track reply context so SMS recipients can reply back to this chat
            if isinstance(destination, SmsAdapter) and destination.phone:
                self.set_reply_context(destination.phone, msg.chat_id)

    # ── Conversation tracker ───────────────────────────────────────────────────

    def _load_cache(self) -> None:
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                raw: dict = json.load(f)
            # JSON keys are always strings; cast back to int
            self._recent_chats = {int(k): v for k, v in raw.items()}
            logger.info("Loaded %d cached conversations from %s", len(self._recent_chats), self._cache_path)
        except FileNotFoundError:
            pass
        except Exception:
            logger.exception("Failed to load recent_chats cache from %s", self._cache_path)

    def _save_cache(self, snapshot: dict) -> None:
        tmp = self._cache_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f)
            os.replace(tmp, self._cache_path)
        except Exception:
            logger.exception("Failed to save recent_chats cache to %s", self._cache_path)

    def _update_recent_chat(self, msg: NormalizedMessage) -> None:
        if msg.chat_id in self._channel_ids:
            return
        snippet = msg.text or msg.caption or (f"<{msg.media_type}>" if msg.media_type else "")
        entry = {
            "chat_id": msg.chat_id,
            "title": msg.chat_title or str(msg.chat_id),
            "last_sender": msg.sender_name,
            "last_text": snippet[:80] if snippet else "",
            "timestamp": msg.timestamp,
        }
        with self._lock:
            self._recent_chats[msg.chat_id] = entry
            if len(self._recent_chats) > _RECENT_CHATS_MAX:
                oldest = min(self._recent_chats, key=lambda k: self._recent_chats[k]["timestamp"])
                del self._recent_chats[oldest]
            snapshot = dict(self._recent_chats)
        self._save_cache(snapshot)

    def _seed_from_history(self, limit: int = 20) -> None:
        """Pre-populate _recent_chats from TDLib chat history on startup."""
        try:
            result = self._client.call_method("getChats", params={"limit": limit})
            result.wait()
            if result.error:
                logger.warning("_seed_from_history: getChats failed: %s", result.error_info)
                return
            chat_ids: list[int] = result.update.get("chat_ids", [])
            logger.info("Seeding recent_chats from %d TDLib chats", len(chat_ids))
            for chat_id in chat_ids:
                with self._lock:
                    if chat_id in self._recent_chats:
                        continue
                gc = self._client.call_method("getChat", params={"chat_id": chat_id})
                gc.wait()
                if gc.error:
                    logger.debug("_seed_from_history: getChat(%s) failed: %s", chat_id, gc.error_info)
                    continue
                chat = gc.update
                # Skip channels (supergroups with is_channel=True)
                chat_type_info = chat.get("type", {})
                if chat_type_info.get("@type") == "chatTypeSupergroup" and chat_type_info.get("is_channel"):
                    self._channel_ids.add(chat_id)
                    continue
                last_msg = chat.get("last_message")
                if not last_msg:
                    continue

                title = chat.get("title") or str(chat_id)

                # Extract text snippet from last message content
                content = last_msg.get("content", {})
                content_type = content.get("@type", "")
                if content_type == "messageText":
                    snippet = (content.get("text") or {}).get("text", "")
                else:
                    snippet = f"<{content_type[len('message'):].lower()}>" if content_type.startswith("message") else ""
                snippet = snippet[:80]

                # Resolve sender name
                sender_info = last_msg.get("sender_id", {})
                sender_type = sender_info.get("@type", "")
                sender_name = "?"
                if sender_type == "messageSenderUser":
                    user_id = sender_info.get("user_id")
                    if user_id:
                        gu = self._client.call_method("getUser", params={"user_id": user_id})
                        gu.wait()
                        if not gu.error:
                            u = gu.update
                            sender_name = " ".join(filter(None, [u.get("first_name"), u.get("last_name")])) or "?"
                elif sender_type == "messageSenderChat":
                    sender_name = title

                timestamp = last_msg.get("date", 0)
                entry = {
                    "chat_id": chat_id,
                    "title": title,
                    "last_sender": sender_name,
                    "last_text": snippet,
                    "timestamp": timestamp,
                }
                with self._lock:
                    self._recent_chats[chat_id] = entry
                    if len(self._recent_chats) > _RECENT_CHATS_MAX:
                        oldest = min(self._recent_chats, key=lambda k: self._recent_chats[k]["timestamp"])
                        del self._recent_chats[oldest]

            with self._lock:
                snapshot = dict(self._recent_chats)
            self._save_cache(snapshot)
            logger.info("Seeded %d conversations from TDLib history", len(snapshot))
        except Exception:
            logger.exception("_seed_from_history failed — continuing without seed")

    def get_conversations(self) -> list[dict]:
        """Return recent chats sorted by most recent first, with 1-based index."""
        with self._lock:
            chats = list(self._recent_chats.values())
        chats.sort(key=lambda c: c["timestamp"], reverse=True)
        chats = chats[:_CONVERSATIONS_LIMIT]
        result = []
        for i, c in enumerate(chats):
            title = c["title"]
            if len(title) > _TITLE_MAX:
                title = title[:_TITLE_MAX - 1] + ">"
            result.append({"index": i + 1, **c, "title": title})
        return result

    # ── Reply context ──────────────────────────────────────────────────────────

    def get_reply_context(self, phone: str) -> Optional[dict]:
        """Return {chat_id, title} for the sticky reply target of this SMS phone, or None."""
        with self._lock:
            chat_id = self._reply_context.get(phone)
            if chat_id is None:
                return None
            chat = self._recent_chats.get(chat_id)
            title = chat["title"] if chat else str(chat_id)
        return {"chat_id": chat_id, "title": title}

    def set_reply_context(self, phone: str, chat_id: int) -> None:
        with self._lock:
            self._reply_context[phone] = chat_id

    # ── Send message ───────────────────────────────────────────────────────────

    def send_message(self, chat_id: int, text: str) -> None:
        """Send a text message to a Telegram chat via TDLib (synchronous)."""
        result = self._client.call_method(
            "sendMessage",
            params={
                "chat_id": chat_id,
                "input_message_content": {
                    "@type": "inputMessageText",
                    "text": {"@type": "formattedText", "text": text},
                },
            },
        )
        result.wait()
        if result.error:
            raise RuntimeError(f"TDLib sendMessage error: {result.error_info}")

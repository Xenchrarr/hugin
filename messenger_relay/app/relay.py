from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from app.config import Config
from app.matrix_client import MatrixClient
from app.models import RoomInfo
from app.normalizer import MatrixEventNormalizer
from app.routing import Route, RouteDispatcher, compile_routes, matches_condition
from app.state import StateStore

logger = logging.getLogger(__name__)


class MessengerRelay:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._matrix = MatrixClient(config.matrix_url, config.matrix_access_token)
        self._dispatcher = RouteDispatcher(config.orchestrator_url, config.service_key)
        self._state = StateStore(config.state_path)
        self._normalizer = MatrixEventNormalizer(
            config.matrix_user_id,
            config.matrix_bridge_bot_user_id,
            config.matrix_ghost_prefix,
        )
        self._rooms: dict[str, RoomInfo] = {}
        self._routes: list[Route] = []
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        actual_user = await self._matrix.whoami()
        if actual_user != self._config.matrix_user_id:
            raise RuntimeError(
                f"Matrix token belongs to {actual_user}, expected {self._config.matrix_user_id}"
            )
        await self.reload_config()
        since = self._state.get_value("matrix_since")
        if not since:
            # Establish a live boundary. Existing timeline events are deliberately
            # not forwarded during first startup.
            initial = await self._matrix.sync(None, timeout_ms=0)
            await self._refresh_rooms(initial)
            since = str(initial["next_batch"])
            self._state.set_value("matrix_since", since)
            logger.info("Established initial Matrix sync boundary")
        self._ready = True
        refresh_task = asyncio.create_task(self._refresh_config_loop())
        try:
            while True:
                try:
                    batch = await self._matrix.sync(since)
                    await self._refresh_rooms(batch)
                    await self._process_batch(batch)
                    since = str(batch["next_batch"])
                    self._state.set_value("matrix_since", since)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Do not advance the sync token. Successful deliveries are
                    # safe to repeat because Message Hub keys them by event and
                    # target; failed deliveries are retried with the same batch.
                    logger.exception("Matrix batch failed; retrying without advancing cursor")
                    await asyncio.sleep(5)
        finally:
            self._ready = False
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)
            await self._dispatcher.aclose()
            await self._matrix.aclose()
            self._state.close()

    async def _refresh_config_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.config_refresh_seconds)
            try:
                await self.reload_config()
            except Exception:
                logger.exception("Could not refresh Messenger relay routes")

    async def reload_config(self) -> None:
        raw = await self._dispatcher.fetch_config()
        routes = compile_routes(raw, self._config.source_endpoint_key)
        with self._lock:
            self._routes = routes
        logger.info("Loaded %d Messenger route(s)", len(routes))

    async def _refresh_rooms(self, batch: dict[str, Any]) -> None:
        joined = ((batch.get("rooms") or {}).get("join") or {})
        for room_id, room_data in joined.items():
            state_events = ((room_data.get("state") or {}).get("events") or [])
            needs_full_state = room_id not in self._rooms or any(
                event.get("type") in {"m.bridge", "uk.half-shot.bridge", "m.room.name", "m.room.member"}
                for event in state_events
            )
            if not needs_full_state:
                continue
            try:
                state = await self._matrix.room_state(room_id)
                info = self._matrix.parse_portal(
                    room_id, state, self._config.matrix_ghost_prefix
                )
            except Exception:
                logger.exception("Could not inspect Matrix room %s", room_id)
                continue
            if info is None:
                with self._lock:
                    self._rooms.pop(room_id, None)
                continue
            with self._lock:
                self._rooms[room_id] = info
            self._state.upsert_conversation(info.thread_id, info.room_id, info.title)

    async def _process_batch(self, batch: dict[str, Any]) -> None:
        joined = ((batch.get("rooms") or {}).get("join") or {})
        for room_id, room_data in joined.items():
            with self._lock:
                room = self._rooms.get(room_id)
            if room is None:
                continue
            events = ((room_data.get("timeline") or {}).get("events") or [])
            for event in events:
                message = self._normalizer.normalize(event, room)
                if message is None:
                    continue
                self._state.upsert_conversation(
                    room.thread_id,
                    room.room_id,
                    room.title,
                    message.sender_name,
                    message.text or message.caption or f"<{message.media_type}>",
                    message.timestamp,
                )
                with self._lock:
                    routes = list(self._routes)
                for route in routes:
                    if not matches_condition(route.condition, message):
                        continue
                    for target in route.targets:
                        await self._dispatcher.dispatch(message, target)
                    logger.info(
                        "Route %r forwarded Messenger event %s", route.name, message.message_id
                    )

    def get_conversations(self) -> list[dict[str, Any]]:
        return self._state.conversations()

    async def send_message(self, thread_id: str, text: str) -> str:
        room_id = self._state.room_for_thread(thread_id)
        if room_id is None:
            raise KeyError(f"Unknown Messenger thread: {thread_id}")
        return await self._matrix.send_text(room_id, text)

    def send_message_from_thread(self, thread_id: str, text: str) -> str:
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Messenger relay is not running")
        future = asyncio.run_coroutine_threadsafe(self.send_message(thread_id, text), self._loop)
        return future.result(timeout=60)

    def get_context(self, phone: str) -> dict[str, Any] | None:
        return self._state.get_context(phone)

    def set_context(self, phone: str, thread_id: str) -> None:
        if self._state.room_for_thread(thread_id) is None:
            raise KeyError(f"Unknown Messenger thread: {thread_id}")
        self._state.set_context(phone, thread_id)

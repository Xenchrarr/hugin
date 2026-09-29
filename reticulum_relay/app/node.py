from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import replace
from typing import Any

from app.announces import AnnounceHandler
from app.config import Config
from app.chat import ChatStore
from app.normalizer import normalize_lxmf
from app.routing import RouteDispatcher
from app.site import NomadSite
from app.state import StateStore

logger = logging.getLogger(__name__)


class AnnounceRateLimitError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Wait {retry_after} seconds before announcing again")
        self.retry_after = retry_after


class ReticulumNode:
    def __init__(
        self,
        config: Config,
        state: StateStore,
        dispatcher: RouteDispatcher,
        chat: ChatStore | None = None,
    ) -> None:
        self.config = config
        self.state = state
        self.dispatcher = dispatcher
        self.chat = chat
        self._outbound_lock = threading.RLock()
        self._announce_lock = threading.RLock()
        self._last_manual_announce: dict[str, float] = {}
        self._last_manual_announce_at: int | None = None
        self._announce_handler = None
        self._ready = False
        self._router = None
        self._delivery_destination = None
        self._site = None
        self._rns = None
        self._lxmf = None

    def start(self) -> None:
        import LXMF
        import RNS

        self._rns = RNS
        self._lxmf = LXMF
        self.config.write_rns_config()
        RNS.Reticulum(configdir=str(self.config.rns_config_path))

        identity = RNS.Identity.from_file(str(self.config.identity_path))
        if identity is None:
            identity = RNS.Identity()
            identity.to_file(str(self.config.identity_path))
            logger.warning("Created new Reticulum identity at %s", self.config.identity_path)

        self._router = LXMF.LXMRouter(
            identity=identity,
            storagepath=str(self.config.lxmf_storage_path),
            name=self.config.node_name,
        )
        self._router.set_message_storage_limit(
            megabytes=self.config.message_storage_megabytes
        )
        self._delivery_destination = self._router.register_delivery_identity(
            identity,
            display_name=self.config.display_name,
            stamp_cost=self.config.inbound_stamp_cost,
        )
        self._router.register_delivery_callback(self._on_delivery)
        if self.config.inbound_stamp_cost is not None:
            self._router.enforce_stamps()

        if self.config.outbound_propagation_node:
            node_hash = self._parse_hash(self.config.outbound_propagation_node)
            self._router.set_outbound_propagation_node(node_hash)
        if self.config.propagation_enabled:
            self._router.enable_propagation()

        self._site = NomadSite(
            RNS,
            identity,
            self.config.pages_path,
            self.config.node_name,
            self.config.announce_interval_seconds,
        )
        if self.chat:
            self._announce_handler = AnnounceHandler(
                RNS, LXMF, self.chat, self.state.remember_contact_name
            )
            RNS.Transport.register_announce_handler(self._announce_handler)
        self._site.start()
        self._router.announce(self._delivery_destination.hash)
        self._ready = True
        logger.info(
            "Reticulum ready: LXMF=%s propagation=%s site=%s",
            self.delivery_hash,
            self.propagation_hash,
            self.site_hash,
        )

    def stop(self) -> None:
        self._ready = False
        if self._announce_handler and self._rns:
            self._rns.Transport.deregister_announce_handler(self._announce_handler)
            self._announce_handler = None
        if self._site:
            self._site.stop()

    @property
    def delivery_hash(self) -> str | None:
        return self._delivery_destination.hash.hex() if self._delivery_destination else None

    @property
    def propagation_hash(self) -> str | None:
        if not self._router or not self.config.propagation_enabled:
            return None
        return self._router.propagation_destination.hash.hex()

    @property
    def site_hash(self) -> str | None:
        return self._site.destination_hash if self._site else None

    def status(self) -> dict[str, Any]:
        store_bytes = None
        peers = 0
        if self._router and self.config.propagation_enabled:
            try:
                store_bytes = self._router.message_storage_size()
                peers = len(self._router.peers)
            except Exception:
                logger.exception("Could not read propagation status")
        return {
            "status": "ok" if self._ready else "starting",
            "ready": self._ready,
            "delivery_hash": self.delivery_hash,
            "propagation_hash": self.propagation_hash,
            "site_hash": self.site_hash,
            "propagation_enabled": self.config.propagation_enabled,
            "message_store_bytes": store_bytes,
            "peers": peers,
            "rnode_enabled": self.config.enable_rnode,
            "tcp_server_enabled": self.config.enable_tcp_server,
            "tcp_listen_port": self.config.tcp_listen_port,
            "last_manual_announce_at": self._last_manual_announce_at,
        }

    def announce(self, target: str = "delivery") -> dict[str, Any]:
        if not self._ready or not self._router or not self._site:
            raise RuntimeError("Reticulum is not ready")
        if target not in {"delivery", "site", "propagation", "all"}:
            raise ValueError("target must be delivery, site, propagation or all")

        targets = ["delivery", "site"] if target == "all" else [target]
        if target == "all" and self.config.propagation_enabled:
            targets.append("propagation")
        if "propagation" in targets and not self.config.propagation_enabled:
            raise ValueError("The LXMF propagation node is not enabled")

        now = time.monotonic()
        with self._announce_lock:
            retry_after = max(
                (
                    math.ceil(10 - (now - self._last_manual_announce[item]))
                    for item in targets
                    if item in self._last_manual_announce
                    and now - self._last_manual_announce[item] < 10
                ),
                default=0,
            )
            if retry_after:
                raise AnnounceRateLimitError(retry_after)

            announced: list[dict[str, str]] = []
            for item in targets:
                if item == "delivery":
                    self._router.announce(self._delivery_destination.hash)
                    destination_hash = self.delivery_hash
                elif item == "site":
                    self._site.announce()
                    destination_hash = self.site_hash
                else:
                    self._router.announce_propagation_node()
                    destination_hash = self.propagation_hash
                self._last_manual_announce[item] = now
                if destination_hash:
                    announced.append({"target": item, "destination_hash": destination_hash})

            self._last_manual_announce_at = int(time.time())
            return {"announced_at": self._last_manual_announce_at, "targets": announced}

    def send(
        self,
        destination_hash: str,
        text: str,
        title: str = "",
        method: str = "direct",
        client_token: str = "",
    ) -> str:
        if not self._ready or not self._router or not self._rns or not self._lxmf:
            raise RuntimeError("Reticulum is not ready")
        if self.chat and client_token:
            cached = self.chat.message_for_token(client_token)
            if cached:
                return str(cached["message_hash"])
        destination_hash_bytes = self._parse_hash(destination_hash)
        methods = {
            "direct": self._lxmf.LXMessage.DIRECT,
            "opportunistic": self._lxmf.LXMessage.OPPORTUNISTIC,
            "propagated": self._lxmf.LXMessage.PROPAGATED,
        }
        if method not in methods:
            raise ValueError("delivery_method must be direct, opportunistic or propagated")
        if method == "propagated" and not self.config.outbound_propagation_node:
            raise ValueError(
                "propagated delivery requires RETICULUM_OUTBOUND_PROPAGATION_NODE"
            )
        identity = self._resolve_identity(destination_hash_bytes)
        destination = self._rns.Destination(
            identity,
            self._rns.Destination.OUT,
            self._rns.Destination.SINGLE,
            "lxmf",
            "delivery",
        )
        with self._outbound_lock:
            if self.chat and client_token:
                cached = self.chat.message_for_token(client_token)
                if cached:
                    return str(cached["message_hash"])
            message = self._lxmf.LXMessage(
                destination,
                self._delivery_destination,
                text,
                title,
                desired_method=methods[method],
                include_ticket=True,
            )
            message.register_delivery_callback(self._on_outbound_state)
            message.register_failed_callback(self._on_outbound_state)
            self._router.handle_outbound(message)
            message_hash = getattr(message, "hash", None)
            if isinstance(message_hash, bytes):
                message_id = message_hash.hex()
            else:
                message_id = str(message_hash or getattr(message, "message_id", ""))
            if not message_id:
                raise RuntimeError("LXMF did not assign a message hash")
            if self.chat:
                self.chat.record_outbound(
                    message,
                    destination_hash.lower(),
                    text,
                    title,
                    self._state_name(getattr(message, "state", None), method),
                    method,
                    client_token,
                )
        known_name = (
            self.chat.display_name_for_destination(destination_hash.lower())
            if self.chat
            else None
        )
        self.state.remember_contact(destination_hash.lower(), known_name, text)
        return message_id

    def _on_outbound_state(self, message) -> None:
        if not self.chat:
            return
        with self._outbound_lock:
            state = self._state_name(
                getattr(message, "state", None),
                self._method_name(getattr(message, "method", None)),
            )
            self.chat.update_outbound(message, state)

    def _state_name(self, state: Any, method: str | None = None) -> str:
        if not self._lxmf:
            return "queued"
        states = {
            self._lxmf.LXMessage.GENERATING: "queued",
            self._lxmf.LXMessage.OUTBOUND: "queued",
            self._lxmf.LXMessage.SENDING: "sending",
            self._lxmf.LXMessage.DELIVERED: "delivered",
            self._lxmf.LXMessage.FAILED: "failed",
            self._lxmf.LXMessage.REJECTED: "rejected",
        }
        if state == self._lxmf.LXMessage.SENT:
            return "stored" if method == "propagated" else "sent"
        return states.get(state, "queued")

    @staticmethod
    def _method_name(value: Any) -> str | None:
        return {1: "opportunistic", 2: "direct", 3: "propagated", 5: "paper"}.get(value)

    def _resolve_identity(self, destination_hash: bytes):
        identity = self._rns.Identity.recall(destination_hash)
        if identity is not None:
            return identity
        self._rns.Transport.request_path(destination_hash)
        deadline = time.monotonic() + self.config.path_timeout_seconds
        while time.monotonic() < deadline:
            if self._rns.Transport.has_path(destination_hash):
                identity = self._rns.Identity.recall(destination_hash)
                if identity is not None:
                    return identity
            time.sleep(0.1)
        raise LookupError(f"No Reticulum path or identity for {destination_hash.hex()}")

    def _on_delivery(self, raw_message) -> None:
        def process() -> None:
            try:
                message = normalize_lxmf(raw_message)
                if not message.message_id or not message.source_hash:
                    raise ValueError("LXMF message has no message or source hash")
                if self.chat and not message.sender_name:
                    announced_name = self.chat.display_name_for_destination(
                        message.source_hash
                    )
                    if announced_name:
                        message = replace(message, sender_name=announced_name)
                if self.chat:
                    self.chat.record_inbound(message, raw_message)
                self.state.remember_contact(
                    message.source_hash, message.sender_name, message.text or message.title
                )
                self.dispatcher.dispatch(message)
            except Exception:
                logger.exception("Could not route inbound LXMF message")

        threading.Thread(target=process, daemon=True, name="lxmf-delivery").start()

    @staticmethod
    def _parse_hash(value: str) -> bytes:
        normalized = value.strip().lower()
        if len(normalized) != 32:
            raise ValueError("Reticulum destination hash must be 32 hexadecimal characters")
        try:
            return bytes.fromhex(normalized)
        except ValueError as exc:
            raise ValueError("Reticulum destination hash must be hexadecimal") from exc

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.config import Config
from app.normalizer import normalize_lxmf
from app.routing import RouteDispatcher
from app.site import NomadSite
from app.state import StateStore

logger = logging.getLogger(__name__)


class ReticulumNode:
    def __init__(self, config: Config, state: StateStore, dispatcher: RouteDispatcher) -> None:
        self.config = config
        self.state = state
        self.dispatcher = dispatcher
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
        }

    def send(
        self,
        destination_hash: str,
        text: str,
        title: str = "",
        method: str = "direct",
    ) -> str:
        if not self._ready or not self._router or not self._rns or not self._lxmf:
            raise RuntimeError("Reticulum is not ready")
        destination_hash_bytes = self._parse_hash(destination_hash)
        identity = self._resolve_identity(destination_hash_bytes)
        destination = self._rns.Destination(
            identity,
            self._rns.Destination.OUT,
            self._rns.Destination.SINGLE,
            "lxmf",
            "delivery",
        )
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
        message = self._lxmf.LXMessage(
            destination,
            self._delivery_destination,
            text,
            title,
            desired_method=methods[method],
            include_ticket=True,
        )
        self._router.handle_outbound(message)
        message_hash = getattr(message, "hash", None)
        if isinstance(message_hash, bytes):
            message_id = message_hash.hex()
        else:
            message_id = str(message_hash or getattr(message, "message_id", ""))
        self.state.remember_contact(destination_hash.lower(), None, text)
        return message_id

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
